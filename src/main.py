import sys
import time
import os
import argparse
import numpy as np
import re
import ctypes
import win32gui
import json

# Add src to python path to allow imports if running directly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.logger import setup_logger
from src.utils.config_loader import ConfigLoader
from src.modules.window_manager import WindowManager
from src.modules.vision_engine import VisionEngine
from src.modules.interaction_simulator import InteractionSimulator
from src.modules.data_processor import DataProcessor

def _normalize_for_match(text):
    if not text:
        return ""
    text = text.upper()
    return re.sub(r"\W+", "", text, flags=re.UNICODE)

def _set_dpi_awareness():
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

def _window_info(hwnd):
    if not hwnd:
        return {"hwnd": 0, "title": "", "class": "", "rect": None}
    try:
        title = win32gui.GetWindowText(hwnd)
    except Exception:
        title = ""
    try:
        cls = win32gui.GetClassName(hwnd)
    except Exception:
        cls = ""
    try:
        rect = win32gui.GetWindowRect(hwnd)
    except Exception:
        rect = None
    return {"hwnd": int(hwnd), "title": title, "class": cls, "rect": rect}

def _guess_source_type(title):
    t = (title or "").lower()
    if "跨屏协作" in (title or ""):
        return "emulator"
    if any(k in t for k in ["emulator", "模拟器", "scrcpy"]):
        return "emulator"
    return "web"

def _extract_publish_time(text, data_processor):
    if not text:
        return ""
    candidates = []
    patterns = [
        r"\d+\s*秒(钟)?前",
        r"\d+\s*分钟?前",
        r"\d+\s*小时(钟)?前",
        r"\d+\s*天前",
        r"昨天(\s*\d{1,2}\s*:\s*\d{1,2})?",
        r"前天(\s*\d{1,2}\s*:\s*\d{1,2})?",
        r"\d{4}\s*[-/.]\s*\d{1,2}\s*[-/.]\s*\d{1,2}",
        r"\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日",
        r"\d{1,2}\s*[-/.]\s*\d{1,2}",
        r"(0?[1-9]|1[0-2])\s+(0?[1-9]|[12]\d|3[01])",
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            candidates.append(m.group(0))
    if not candidates:
        return ""
    return data_processor.parse_time(candidates[0])

def _extract_title(text):
    if not text:
        return ""
    for line in (text or "").splitlines():
        line = line.strip()
        if len(line) >= 4 and "关注" not in line:
            return line[:60]
    return ""

def _extract_author(text):
    if not text:
        return ""
    for line in (text or "").splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("@") and len(s) > 1:
            return s[1:40]
        if "关注" in s:
            left = s.split("关注", 1)[0].strip()
            left = re.sub(r"[\W_]+", "", left, flags=re.UNICODE)
            if 1 < len(left) <= 20:
                return left
    return ""

def main():
    _set_dpi_awareness()

    parser = argparse.ArgumentParser(description="Fisher - Xiaohongshu Scraper")
    parser.add_argument("--window", "-w", help="Target window title pattern (regex)", default=None)
    args = parser.parse_args()

    # 1. Initialize
    logger = setup_logger()
    logger.info("Starting Fisher - Xiaohongshu Scraper")
    
    try:
        config_loader = ConfigLoader()
        logger.info("Configuration loaded")
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return

    # 2. Setup Modules
    window_manager = WindowManager(logger)
    vision_engine = VisionEngine(logger, config_loader.get_ocr_config())
    interaction = InteractionSimulator(logger, config_loader.get_scroll_config())
    data_processor = DataProcessor(logger, config_loader.get_output_config())
    visited_posts = set()

    # 3. Window Selection
    if args.window:
        if not window_manager.select_window_by_pattern(args.window):
             logger.error("No window selected. Exiting.")
             return
    else:
        logger.info("Please select the target window (Browser or Emulator)...")
        if not window_manager.select_window_interactive():
            logger.error("No window selected. Exiting.")
            return

    # Focus window
    window_manager.focus_window()
    
    # Set target window for background interaction
    if window_manager.target_hwnd:
        input_hwnd = window_manager.find_input_window(window_manager.target_hwnd)
        interaction.set_target_window(input_hwnd)
    source_type = config_loader.get("source_type", _guess_source_type(window_manager.target_title))

    time.sleep(1) # Wait for window to come to front

    # 4. Main Loop (Simplified for Demo)
    logger.info("Starting main scraping loop. Press Ctrl+C to stop.")
    try:
        next_scroll_mode = "drag"
        while True:
            rect = window_manager.get_client_screen_rect()
            if not rect:
                logger.error("Window lost.")
                break

            logger.info("Capturing screen...")
            capture_method = config_loader.get("capture_method", "screen")
            debug_dump = bool(config_loader.get("debug_dump", False))
            debug_folder = config_loader.get("debug_folder", os.path.join("result", "debug"))
            debug_log_path = None

            if capture_method == "printwindow":
                image = vision_engine.capture_window(window_manager.target_hwnd)
                if image is None:
                    logger.warning("PrintWindow capture returned empty. Falling back to screen capture.")
                    image = vision_engine.capture_screen(rect)
            else:
                if win32gui.GetForegroundWindow() != window_manager.target_hwnd:
                    window_manager.focus_window()
                    time.sleep(0.1)
                image = vision_engine.capture_screen(rect)

            before_image = image

            if debug_dump and image is not None:
                os.makedirs(debug_folder, exist_ok=True)
                ts = time.strftime("%Y%m%d_%H%M%S")
                debug_log_path = os.path.join(debug_folder, f"debug_{ts}.log")
                image.save(os.path.join(debug_folder, f"capture_{ts}.png"))
                target = _window_info(window_manager.target_hwnd)
                fg = _window_info(win32gui.GetForegroundWindow())
                input_target = _window_info(getattr(interaction, "hwnd", None))
                with open(debug_log_path, "w", encoding="utf-8") as f:
                    f.write(f"capture_method={capture_method}\n")
                    f.write(f"client_screen_rect={rect}\n")
                    f.write(f"next_scroll_mode={next_scroll_mode}\n")
                    f.write(f"target_hwnd={target}\n")
                    f.write(f"input_hwnd={input_target}\n")
                    f.write(f"foreground_hwnd={fg}\n")
            
            # OCR & Analyze
            logger.info("Analyzing page layout...")
            layout_info = vision_engine.analyze_page(image)
            
            content_rect = None
            posts = []
            
            if layout_info:
                header_rect = layout_info["safe_area"]["header"]
                footer_rect = layout_info["safe_area"]["footer"]
                content_rect = layout_info["safe_area"]["content"]
                posts = layout_info["posts"]
                
                # Draw debug info for layout
                if debug_dump and image:
                    import cv2
                    debug_img = np.array(image)
                    debug_img = cv2.cvtColor(debug_img, cv2.COLOR_RGB2BGR)
                    
                    # Draw header (Red)
                    cv2.rectangle(debug_img, (header_rect[0], header_rect[1]), (header_rect[2], header_rect[3]), (0, 0, 255), 2)
                    # Draw footer (Blue)
                    cv2.rectangle(debug_img, (footer_rect[0], footer_rect[1]), (footer_rect[2], footer_rect[3]), (255, 0, 0), 2)
                    # Draw content (Green)
                    cv2.rectangle(debug_img, (content_rect[0], content_rect[1]), (content_rect[2], content_rect[3]), (0, 255, 0), 2)
                    
                    for p in posts:
                        rx, ry, rw, rh = p["rect"]
                        cv2.rectangle(debug_img, (rx, ry), (rx+rw, ry+rh), (0, 255, 255), 2)
                        
                    os.makedirs(debug_folder, exist_ok=True)
                    cv2.imwrite(os.path.join(debug_folder, f"layout_{ts}.png"), debug_img)
            
            # If layout analysis failed or returned no posts, fallback to full page text
            full_text = ""
            if not posts:
                full_text = vision_engine.extract_text(image)
            
            keywords = config_loader.get("keywords", [])
            found_post = None
            
            # Check posts one by one
            for post in posts:
                post_text = vision_engine.extract_text(post["image"])
                norm_post_text = _normalize_for_match(post_text)
                
                post_matched = []
                for k in keywords:
                    if not k: continue
                    if k in post_text:
                        post_matched.append(k)
                        continue
                    nk = _normalize_for_match(k)
                    if nk and nk in norm_post_text:
                        post_matched.append(k)
                
                if post_matched:
                    # Check if visited
                    key_lines = []
                    for line in (post_text or "").splitlines():
                        s = line.strip()
                        if not s or "关注" in s: continue
                        key_lines.append(s)
                        if len(key_lines) >= 3: break
                    
                    post_key = _normalize_for_match(" ".join(key_lines))[:100]
                    
                    if post_key and post_key in visited_posts:
                        continue
                        
                    logger.info(f"Found keywords {post_matched} in post: {post_key}")
                    found_post = {
                        "rect": post["rect"],
                        "text": post_text,
                        "key": post_key,
                        "matched": post_matched
                    }
                    break
            
            # Fallback for full text (if no posts detected)
            if not found_post and full_text:
                 # ... existing full text logic ...
                 pass 

            last_action = "none"
            
            if found_post:
                rx, ry, rw, rh = found_post["rect"]
                cx = rx + rw // 2
                cy = ry + rh // 2
                
                # Check safe area
                is_safe = True
                if layout_info:
                    header = layout_info["safe_area"]["header"]
                    footer = layout_info["safe_area"]["footer"]
                    # Check if center point is in header or footer
                    if (header[0] <= cx <= header[2] and header[1] <= cy <= header[3]) or \
                       (footer[0] <= cx <= footer[2] and footer[1] <= cy <= footer[3]):
                        logger.warning(f"Click point ({cx},{cy}) is in unsafe area. Skipping.")
                        is_safe = False
                
                if is_safe:
                    visited_posts.add(found_post["key"])
                    
                    # Calculate click point relative to client area
                    # rect is (screen_left, screen_top, ...)
                    # We need client coordinates for interaction
                    # But wait, capture_screen uses screen coordinates.
                    # Interaction uses client coordinates.
                    # We need to map screen point (cx, cy) to client point.
                    # WindowManager.get_client_screen_rect returns screen coordinates of client area.
                    client_screen_left, client_screen_top, _, _ = rect
                    
                    # The image captured corresponds to 'rect' (client area in screen coords)
                    # So (cx, cy) is relative to the image (0,0 is top-left of image)
                    # which IS (0,0) of client area.
                    # So cx, cy are already client coordinates!
                    
                    open_x, open_y = cx, cy
                    
                    interaction.click(open_x, open_y, safe_check=True, forbidden_rects=[layout_info["safe_area"]["header"], layout_info["safe_area"]["footer"]] if layout_info else None)
                    last_action = "open"
                    time.sleep(float(config_loader.get("open_wait_seconds", 1.2)))
                    
                    # ... Detail scraping logic (reuse existing) ...
                    # For MVP, we just copy-paste or wrap the detail logic into a function
                    # To keep it simple, I will call a helper or inline it.
                    # Let's reuse the existing detail scraping block
                    
                    # --- Start Detail Scraping ---
                    detail_max_pages = int(config_loader.get("detail_max_pages", 3))
                    detail_scroll_pause = float(config_loader.get("detail_scroll_pause", 1.0))
                    detail_content_max_chars = int(config_loader.get("detail_content_max_chars", 8000))

                    page_images = []
                    page_texts = []
                    page_image_texts = []

                    capture_method = config_loader.get("capture_method", "screen")
                    last_thumb = None

                    for page_idx in range(max(1, detail_max_pages)):
                        rect_detail = window_manager.get_client_screen_rect()
                        if capture_method == "printwindow":
                            detail_image = vision_engine.capture_window(window_manager.target_hwnd)
                            if detail_image is None:
                                detail_image = vision_engine.capture_screen(rect_detail)
                        else:
                            detail_image = vision_engine.capture_screen(rect_detail)

                        if detail_image is None:
                            break

                        page_images.append(detail_image)
                        detail_text = vision_engine.extract_text(detail_image)
                        page_texts.append(detail_text or "")

                        w, h = detail_image.size
                        crop = detail_image.crop((int(w * 0.1), int(h * 0.25), int(w * 0.9), int(h * 0.85)))
                        crop_text = vision_engine.extract_text(crop)
                        if crop_text:
                            page_image_texts.append(crop_text)

                        thumb = np.array(detail_image.convert("L").resize((120, 120)), dtype=np.int16)
                        if last_thumb is not None:
                            diff = float(np.mean(np.abs(thumb - last_thumb)))
                            if diff < float(config_loader.get("detail_scroll_verify_threshold", 1.5)):
                                break
                        last_thumb = thumb

                        if page_idx < detail_max_pages - 1:
                            interaction.scroll_down()
                            time.sleep(detail_scroll_pause)

                    merged_lines = []
                    seen = set()
                    for t in page_texts:
                        for line in (t or "").splitlines():
                            s = line.strip()
                            if not s:
                                continue
                            key = _normalize_for_match(s)
                            if not key or key in seen:
                                continue
                            seen.add(key)
                            merged_lines.append(s)
                    merged_content = "\n".join(merged_lines)[:detail_content_max_chars]

                    images_text = []
                    seen_img = set()
                    for t in page_image_texts:
                        s = (t or "").strip()
                        if not s:
                            continue
                        key = _normalize_for_match(s)
                        if key and key not in seen_img:
                            seen_img.add(key)
                            images_text.append(s[:2000])

                    title = _extract_title(page_texts[0] if page_texts else "") or _extract_title(found_post["text"])
                    author = _extract_author(page_texts[0] if page_texts else "")
                    publish_time = _extract_publish_time(page_texts[0] if page_texts else "", data_processor)

                    data = {
                        "title": title,
                        "author": author,
                        "publish_time": publish_time,
                        "content": merged_content,
                        "images_text": images_text,
                        "keywords_matched": found_post["matched"],
                        "source_type": source_type,
                        "clicked": {"x": open_x, "y": open_y}
                    }
                    data_processor.save_post(data)
                    if debug_dump:
                        os.makedirs(debug_folder, exist_ok=True)
                        ts = time.strftime("%Y%m%d_%H%M%S")
                        with open(os.path.join(debug_folder, f"post_{ts}.json"), "w", encoding="utf-8") as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)

                    if debug_dump and page_images:
                        os.makedirs(debug_folder, exist_ok=True)
                        ts = time.strftime("%Y%m%d_%H%M%S")
                        for idx, img in enumerate(page_images):
                            img.save(os.path.join(debug_folder, f"detail_{ts}_{idx}.png"))
                        with open(os.path.join(debug_folder, f"detail_ocr_{ts}.txt"), "w", encoding="utf-8") as f:
                            f.write("\n\n---PAGE---\n\n".join(page_texts))

                    back_mode = config_loader.get("back_mode", "click")
                    if back_mode == "esc":
                        interaction.return_back()
                    else:
                        back_x_ratio = float(config_loader.get("back_click_x_ratio", 0.08))
                        back_y_ratio = float(config_loader.get("back_click_y_ratio", 0.08))
                        back_x = max(0, min(client_w - 1, int(client_w * back_x_ratio)))
                        back_y = max(0, min(client_h - 1, int(client_h * back_y_ratio)))
                        interaction.click(back_x, back_y)
                    time.sleep(float(config_loader.get("back_wait_seconds", 1.0)))
                    time.sleep(2)
                    continue
                    # --- End Detail Scraping ---

            else:
                logger.info("No keywords found in any posts. Scrolling...")
                if next_scroll_mode == "wheel":
                    interaction.scroll_down_wheel()
                else:
                    interaction.scroll_down(region=content_rect)
                last_action = "scroll"


            time.sleep(0.4)

            if last_action == "scroll":
                rect_after = window_manager.get_client_screen_rect()
                if capture_method == "printwindow":
                    after_image = vision_engine.capture_window(window_manager.target_hwnd)
                else:
                    after_image = vision_engine.capture_screen(rect_after)

                diff_threshold = float(config_loader.get("scroll_verify_threshold", 2.5))
                if before_image is not None and after_image is not None:
                    a = np.array(before_image.convert("L").resize((200, 200)), dtype=np.int16)
                    b = np.array(after_image.convert("L").resize((200, 200)), dtype=np.int16)
                    diff = float(np.mean(np.abs(a - b)))
                    if diff < diff_threshold:
                        logger.warning("Scroll verification failed. Will use wheel on next scroll.")
                        next_scroll_mode = "wheel"
                    else:
                        next_scroll_mode = "drag"

            # Pause between iterations
            time.sleep(2)

    except KeyboardInterrupt:
        logger.info("Stopped by user.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")

if __name__ == "__main__":
    main()
