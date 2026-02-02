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

class VisionEngine:
    def __init__(self, logger, ocr_config):
        self.logger = logger
        self.config = ocr_config
        self._setup_tesseract()

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
        """Find location of specific text in image (not fully implemented in MVP)."""
        # This would require using image_to_data to get bounding boxes
        pass
