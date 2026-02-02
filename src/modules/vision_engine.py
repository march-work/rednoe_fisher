import cv2
import numpy as np
import pytesseract
from PIL import Image, ImageGrab
import os
import win32gui
import win32ui
import win32con
import ctypes
import re

from src.modules.layout_analysis import LayoutAnalyzer

class VisionEngine:
    def __init__(self, logger, ocr_config, layout_config=None, setup_tesseract=True):
        self.logger = logger
        self.config = ocr_config
        self.layout_analyzer = LayoutAnalyzer(config=layout_config)
        if setup_tesseract:
            self._setup_tesseract()

    def analyze_page(self, image):
        """
        Analyze the full page to find safe areas and segment posts.
        """
        if image is None:
            return None
            
        width, height = image.size
        header, footer, content = self.layout_analyzer.detect_safe_area(width, height)
        
        posts = self.layout_analyzer.segment_waterfall_flow(image, content)
        
        return {
            "safe_area": {
                "header": header,
                "footer": footer,
                "content": content
            },
            "posts": posts
        }

    def extract_text_with_confidence(self, image, psm=None, lang=None):
        if image is None:
            return {"text": "", "avg_conf": 0.0, "tokens": [], "cjk_ratio": 0.0}

        try:
            processed_img = self.preprocess_image(image)
            lang = lang or self.config.get("language", "chi_sim")
            psm = int(psm if psm is not None else self.config.get("psm", 6))

            data = pytesseract.image_to_data(
                processed_img,
                lang=lang,
                config=f"--psm {psm}",
                output_type=pytesseract.Output.DICT,
            )
            tokens = []
            confs = []
            parts = []
            n = len(data.get("text", []))
            for i in range(n):
                raw = (data.get("text", [""])[i] or "").strip()
                if not raw:
                    continue
                try:
                    conf = float(data.get("conf", ["-1"])[i])
                except Exception:
                    conf = -1.0
                parts.append(raw)
                tokens.append({"text": raw, "conf": conf})
                if conf >= 0:
                    confs.append(conf)

            text = " ".join(parts).strip()
            avg_conf = float(sum(confs) / len(confs)) if confs else 0.0
            cjk = re.findall(r"[\u4e00-\u9fff]", text)
            cjk_ratio = float(len(cjk) / max(1, len(text)))
            return {"text": text, "avg_conf": avg_conf, "tokens": tokens, "cjk_ratio": cjk_ratio}
        except Exception as e:
            self.logger.error(f"OCR extraction failed: {e}")
            return {"text": "", "avg_conf": 0.0, "tokens": [], "cjk_ratio": 0.0}


    def _setup_tesseract(self):
        # Attempt to find tesseract executable in common locations if not in PATH
        possible_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            os.environ.get("TESSERACT_CMD", "")
        ]
        
        found = False
        for path in possible_paths:
            if path and os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                self.logger.info(f"Tesseract found at: {path}")
                found = True
                break
        
        if not found:
            # Check if it's in PATH by running it
            try:
                pytesseract.get_tesseract_version()
                found = True
                self.logger.info("Tesseract found in system PATH")
            except:
                self.logger.warning("Tesseract-OCR executable not found. OCR features will fail.")
                self.logger.warning("Please install Tesseract-OCR and add it to PATH or set TESSERACT_CMD.")

    def capture_screen(self, rect):
        """Capture screen content within the given rectangle (left, top, right, bottom)."""
        if not rect:
            return None
        try:
            # ImageGrab expects (bbox) which is compatible with rect tuple
            image = ImageGrab.grab(bbox=rect)
            return image
        except Exception as e:
            self.logger.error(f"Screen capture failed: {e}")
            return None

    def capture_window(self, hwnd):
        if not hwnd:
            return None
        try:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            width = right - left
            height = bottom - top

            hwnd_dc = win32gui.GetWindowDC(hwnd)
            mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
            save_dc = mfc_dc.CreateCompatibleDC()

            save_bitmap = win32ui.CreateBitmap()
            save_bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
            save_dc.SelectObject(save_bitmap)

            result = ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 0)

            bmpinfo = save_bitmap.GetInfo()
            bmpstr = save_bitmap.GetBitmapBits(True)
            image = Image.frombuffer(
                "RGB",
                (bmpinfo["bmWidth"], bmpinfo["bmHeight"]),
                bmpstr,
                "raw",
                "BGRX",
                0,
                1
            )

            win32gui.DeleteObject(save_bitmap.GetHandle())
            save_dc.DeleteDC()
            mfc_dc.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwnd_dc)

            if result != 1:
                return None

            return image
        except Exception as e:
            self.logger.error(f"Window capture failed: {e}")
            return None

    def preprocess_image(self, image):
        """Convert PIL image to OpenCV format and preprocess for OCR."""
        img_np = np.array(image)
        img_cv = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        scale = float(self.config.get("scale", 2.0))
        if scale and abs(scale - 1.0) > 1e-6:
            gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

        blur = int(self.config.get("median_blur", 3))
        if blur and blur > 1:
            if blur % 2 == 0:
                blur += 1
            gray = cv2.medianBlur(gray, blur)

        mode = self.config.get("threshold", "otsu")
        if mode == "adaptive":
            block = int(self.config.get("adaptive_block_size", 31))
            if block % 2 == 0:
                block += 1
            c = int(self.config.get("adaptive_c", 5))
            return cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block, c)

        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return binary

    def extract_text(self, image):
        """Extract text from a PIL Image using OCR."""
        try:
            # Convert to appropriate format if needed, but pytesseract handles PIL images
            processed_img = self.preprocess_image(image)
            
            # config params
            lang = self.config.get("language", "chi_sim")
            psm = self.config.get("psm", 6)
            
            text = pytesseract.image_to_string(processed_img, lang=lang, config=f'--psm {psm}')
            return text.strip()
        except Exception as e:
            self.logger.error(f"OCR extraction failed: {e}")
            return ""

    def find_keyword_click_point(self, image, keywords):
        try:
            for k in (keywords or []):
                pt = self.find_text_location(image, k)
                if pt:
                    return pt

            processed_img = self.preprocess_image(image)
            lang = self.config.get("language", "chi_sim")
            psm = self.config.get("psm", 6)
            scale = float(self.config.get("scale", 2.0))
            if not scale:
                scale = 1.0

            norm_keywords = []
            for k in (keywords or []):
                if not k:
                    continue
                nk = re.sub(r"\W+", "", str(k), flags=re.UNICODE).upper()
                if nk:
                    norm_keywords.append(nk)
            if not norm_keywords:
                return None

            data = pytesseract.image_to_data(processed_img, lang=lang, config=f'--psm {psm}', output_type=pytesseract.Output.DICT)
            n = len(data.get("text", []))

            groups = {}
            for i in range(n):
                block_nums = data.get("block_num", None)
                par_nums = data.get("par_num", None)
                line_nums = data.get("line_num", None)
                key = (
                    int(block_nums[i]) if block_nums else 0,
                    int(par_nums[i]) if par_nums else 0,
                    int(line_nums[i]) if line_nums else 0,
                )
                groups.setdefault(key, []).append(i)

            best = None
            best_score = -1.0

            for idxs in groups.values():
                pieces = []
                confs = []
                lefts = []
                tops = []
                rights = []
                bottoms = []

                for i in idxs:
                    word = (data["text"][i] or "").strip()
                    if not word:
                        continue
                    try:
                        conf = float(data.get("conf", ["-1"])[i])
                    except Exception:
                        conf = -1.0
                    if conf >= 0:
                        confs.append(conf)
                    pieces.append(word)

                    l = float(data["left"][i])
                    t = float(data["top"][i])
                    w = float(data["width"][i])
                    h = float(data["height"][i])
                    lefts.append(l)
                    tops.append(t)
                    rights.append(l + w)
                    bottoms.append(t + h)

                if not pieces or not lefts:
                    continue

                line_text = "".join(pieces)
                norm_line = re.sub(r"\W+", "", line_text, flags=re.UNICODE).upper()
                if not norm_line:
                    continue

                hit = False
                for nk in norm_keywords:
                    if nk in norm_line or norm_line in nk:
                        hit = True
                        break
                if not hit:
                    continue

                avg_conf = float(sum(confs) / len(confs)) if confs else 0.0
                l = min(lefts)
                t = min(tops)
                r = max(rights)
                b = max(bottoms)
                cx = ((l + r) / 2.0) / scale
                cy = ((t + b) / 2.0) / scale
                pt = (int(cx), int(cy))
                if avg_conf > best_score:
                    best_score = avg_conf
                    best = pt

            return best
        except Exception as e:
            self.logger.error(f"Keyword location failed: {e}")
            return None

    def find_text_location(self, image, target_text):
        if image is None or not target_text:
            return None

        try:
            processed_img = self.preprocess_image(image)
            lang = self.config.get("language", "chi_sim")
            psm = self.config.get("psm", 6)
            scale = float(self.config.get("scale", 2.0))
            if not scale:
                scale = 1.0

            def _norm(s):
                return re.sub(r"\W+", "", str(s), flags=re.UNICODE).upper()

            target_norm = _norm(target_text)
            if not target_norm:
                return None

            data = pytesseract.image_to_data(
                processed_img,
                lang=lang,
                config=f"--psm {psm}",
                output_type=pytesseract.Output.DICT,
            )
            n = len(data.get("text", []))

            groups = {}
            for i in range(n):
                block_nums = data.get("block_num", None)
                par_nums = data.get("par_num", None)
                line_nums = data.get("line_num", None)
                key = (
                    int(block_nums[i]) if block_nums else 0,
                    int(par_nums[i]) if par_nums else 0,
                    int(line_nums[i]) if line_nums else 0,
                )
                groups.setdefault(key, []).append(i)

            best_pt = None
            best_score = -1.0

            for idxs in groups.values():
                tokens = []
                joined = ""
                cursor = 0

                for i in idxs:
                    raw = (data.get("text", [""])[i] or "").strip()
                    if not raw:
                        continue
                    tnorm = _norm(raw)
                    if not tnorm:
                        continue
                    try:
                        conf = float(data.get("conf", ["-1"])[i])
                    except Exception:
                        conf = -1.0

                    l = float(data.get("left", [0])[i])
                    t = float(data.get("top", [0])[i])
                    w = float(data.get("width", [0])[i])
                    h = float(data.get("height", [0])[i])

                    start = cursor
                    end = cursor + len(tnorm)
                    cursor = end
                    joined += tnorm
                    tokens.append(
                        {
                            "start": start,
                            "end": end,
                            "conf": conf,
                            "left": l,
                            "top": t,
                            "right": l + w,
                            "bottom": t + h,
                        }
                    )

                if not joined or not tokens:
                    continue

                pos = joined.find(target_norm)
                if pos < 0:
                    continue

                span_start = pos
                span_end = pos + len(target_norm)
                cov = [tok for tok in tokens if tok["end"] > span_start and tok["start"] < span_end]
                if not cov:
                    continue

                left = min(tok["left"] for tok in cov)
                top = min(tok["top"] for tok in cov)
                right = max(tok["right"] for tok in cov)
                bottom = max(tok["bottom"] for tok in cov)

                confs = [tok["conf"] for tok in cov if tok["conf"] >= 0]
                avg_conf = float(sum(confs) / len(confs)) if confs else 0.0
                score = avg_conf + (len(target_norm) / max(1, len(joined))) * 20.0

                cx = ((left + right) / 2.0) / scale
                cy = ((top + bottom) / 2.0) / scale
                pt = (int(cx), int(cy))

                if score > best_score:
                    best_score = score
                    best_pt = pt

            return best_pt
        except Exception as e:
            self.logger.error(f"Text location failed: {e}")
            return None
