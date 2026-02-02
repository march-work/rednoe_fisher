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
from src.utils.open_guard import update_confirm
from src.utils.keyword_matcher import match_keywords
from src.utils.opacity import percent_to_alpha
from src.modules.window_manager import WindowManager
from src.modules.vision_engine import VisionEngine
from src.modules.interaction_simulator import InteractionSimulator
from src.modules.data_processor import DataProcessor
from src.utils.coords import CoordinateSpace
from src.modules.processed_store import ProcessedPostStore, signature_from_text, signature_from_image

def _normalize_for_match(text):
    if not text:
        return ""
    text = text.upper()
    return re.sub(r"\W+", "", text, flags=re.UNICODE)

def _confirm_key(sig, title_text):
    s = (sig or "").strip()
    if s:
        return s[:12]
    return _normalize_for_match(title_text)[:120]

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

def _rect_contains(outer, x, y, margin=0):
    if not outer:
        return False
    l, t, r, b = outer
    return (l + margin) <= x <= (r - margin) and (t + margin) <= y <= (b - margin)

def _rect_inside(outer, inner, margin=0):
    if not outer or not inner:
        return False
    ol, ot, orr, ob = outer
    il, it, ir, ib = inner
    return (
        (ol + margin) <= il and (ot + margin) <= it and (orr - margin) >= ir and (ob - margin) >= ib
    )

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
    vision_engine = VisionEngine(logger, config_loader.get_ocr_config(), layout_config=config_loader.get_layout_config())
    overlay_opacity_percent = float(config_loader.get("overlay_opacity_percent", 10.0))
    overlay_mask_opacity_percent = config_loader.get("overlay_mask_opacity_percent", 15.0)
    overlay_fg_opacity_percent = config_loader.get("overlay_fg_opacity_percent", 80.0)
    overlay_mask_alpha = percent_to_alpha(overlay_mask_opacity_percent, default=overlay_opacity_percent)
    overlay_fg_alpha = percent_to_alpha(overlay_fg_opacity_percent, default=overlay_opacity_percent)
    interaction = InteractionSimulator(
        logger,
        config_loader.get_scroll_config(),
        emulator_overlay_mask_alpha=overlay_mask_alpha,
        emulator_overlay_fg_alpha=overlay_fg_alpha,
    )
    data_processor = DataProcessor(logger, config_loader.get_output_config())
    coords = CoordinateSpace()
    processed_path = str(config_loader.get("processed_store_path", os.path.join("result", "processed_posts.json")))
    processed_store = ProcessedPostStore(processed_path, max_size=int(config_loader.get("processed_store_max", 5000)))
    visited_posts = set()
    startup_t0 = time.monotonic()
    startup_skip_open_seconds = float(config_loader.get("startup_skip_open_seconds", 2.5))
    skip_open_until = startup_t0 + max(0.0, startup_skip_open_seconds)
    open_on_match = bool(config_loader.get("open_on_match", True))
    match_confirm_frames = int(config_loader.get("match_confirm_frames", 2))
    pending_key = None
    pending_count = 0
    min_ocr_avg_conf = float(config_loader.get("min_ocr_avg_conf", 55.0))
    min_ocr_token_conf = float(config_loader.get("min_ocr_token_conf", 60.0))
    min_ocr_cjk_ratio = float(config_loader.get("min_ocr_cjk_ratio", 0.02))

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
        coords.set_target(input_hwnd)
    source_type = config_loader.get("source_type", _guess_source_type(window_manager.target_title))

    time.sleep(1) # Wait for window to come to front

    # 4. Main Loop (Simplified for Demo)
    logger.info("Starting main scraping loop. Press Ctrl+C to stop.")
    try:
        next_scroll_mode = "drag"
        last_list_thumb = None
        list_stable_frames = 0
        needs_reanalyze = True
        last_action = "none"
        last_action_ts = 0.0
        while True:
            rect = window_manager.get_client_screen_rect(getattr(interaction, "hwnd", None))
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

            list_page_stable_threshold = float(config_loader.get("list_page_stable_threshold", 1.5))
            list_min_stable_frames = int(config_loader.get("list_min_stable_frames", 2))
            static_sleep_seconds = float(config_loader.get("static_sleep_seconds", 0.25))
            scroll_retry_seconds = float(config_loader.get("scroll_retry_seconds", 1.0))
            scroll_settle_seconds = float(config_loader.get("scroll_settle_seconds", 0.35))

            if image is not None:
                try:
                    thumb = np.array(image.convert("L").resize((120, 120)), dtype=np.int16)
                except Exception:
                    thumb = None

                diff = None
                if thumb is not None and last_list_thumb is not None:
                    try:
                        diff = float(np.mean(np.abs(thumb - last_list_thumb)))
                    except Exception:
                        diff = None
                last_list_thumb = thumb

                page_stable = diff is not None and diff < list_page_stable_threshold
                if page_stable:
                    list_stable_frames += 1
                else:
                    list_stable_frames = 0

                now_mono = time.monotonic()
                if (
                    needs_reanalyze
                    and page_stable
                    and last_action == "scroll"
                    and (now_mono - float(last_action_ts or 0.0)) >= scroll_retry_seconds
                ):
                    if next_scroll_mode == "wheel":
                        interaction.scroll_down_wheel()
                    else:
                        interaction.scroll_down(region=None)
                    last_action = "scroll"
                    last_action_ts = now_mono
                    list_stable_frames = 0
                    time.sleep(0.2)
                    continue

                if (not needs_reanalyze) and page_stable and list_stable_frames >= list_min_stable_frames:
                    time.sleep(static_sleep_seconds)
                    continue
                if not needs_reanalyze:
                    time.sleep(static_sleep_seconds)
                    continue

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
            now_mono = time.monotonic()
            force_ready = (last_action != "scroll") or (
                (now_mono - float(last_action_ts or 0.0)) >= scroll_settle_seconds
            )
            if image is not None and (list_stable_frames < list_min_stable_frames) and (not force_ready):
                time.sleep(0.05)
                continue
            layout_info = vision_engine.analyze_page(image)
            needs_reanalyze = False
            
            content_rect = None
            posts = []
            
            if layout_info:
                header_rect = layout_info["safe_area"]["header"]
                footer_rect = layout_info["safe_area"]["footer"]
                content_rect = layout_info["safe_area"]["content"]
                posts = layout_info["posts"]

                try:
                    client_screen_rect = coords.get_client_screen_rect()
                except Exception:
                    client_screen_rect = rect
                
                active_card = None
                if posts and content_rect:
                    cx0 = int((content_rect[0] + content_rect[2]) / 2)
                    cy0 = int(content_rect[1] + (content_rect[3] - content_rect[1]) * 0.5)
                    best = None
                    best_score = 1e18
                    for p in posts:
                        cl, ct, cr, cb = p.click_rect
                        pcx = int((cl + cr) / 2)
                        pcy = int((ct + cb) / 2)
                        dy = abs(pcy - cy0)
                        dx = abs(pcx - cx0)
                        score = dy * 3 + dx
                        if best is None or score < best_score:
                            best = p
                            best_score = score
                    active_card = best

                overlay_state = {
                    "mask": True,
                    "content_rect": content_rect,
                    "active_rect": active_card.rect if active_card else None,
                    "cards": [],
                }
                for idx, p in enumerate(posts[:30], start=1):
                    dashed = False
                    try:
                        dashed = not p.is_complete(content_rect)
                    except Exception:
                        dashed = False
                    overlay_state["cards"].append(
                        {
                            "idx": idx,
                            "rect": p.rect,
                            "image_rect": getattr(p, "image_rect", None),
                            "title_rect": p.title_rect,
                            "meta_rect": getattr(p, "meta_rect", None),
                            "click_rect": p.click_rect,
                            "dashed": dashed,
                            "label": f"Post-{idx}",
                        }
                    )
                try:
                    interaction.update_emulator_overlay(client_screen_rect, overlay_state)
                except Exception as e:
                    logger.error(f"Emulator overlay update failed: {e}")
                    if debug_log_path:
                        with open(debug_log_path, "a", encoding="utf-8") as f:
                            f.write(f"overlay_update_failed={e}\n")

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
                    
                    for idx, p in enumerate(posts[:30], start=1):
                        l, t, r, b = p.rect
                        img_rect = getattr(p, "image_rect", None)
                        tl, tt, tr, tb = p.title_rect
                        meta_rect = getattr(p, "meta_rect", None)
                        cl, ct, cr, cb = p.click_rect
                        complete = False
                        try:
                            complete = p.is_complete(content_rect)
                        except Exception:
                            complete = False
                        color = (0, 0, 255) if complete else (0, 0, 180)
                        cv2.rectangle(debug_img, (l, t), (r, b), color, 1)
                        cv2.putText(debug_img, f"Post-{idx}", (l + 4, t + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
                        if img_rect:
                            il, it, ir, ib = img_rect
                            cv2.rectangle(debug_img, (il, it), (ir, ib), (255, 255, 0), 1)
                            cv2.putText(debug_img, f"img{idx}", (il + 6, it + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                        cv2.rectangle(debug_img, (tl, tt), (tr, tb), (0, 165, 255), 1)
                        cv2.putText(debug_img, f"title{idx}", (tl + 6, tt + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)
                        if meta_rect:
                            ml, mt, mr, mb = meta_rect
                            cv2.rectangle(debug_img, (ml, mt), (mr, mb), (255, 0, 255), 1)
                            cv2.putText(debug_img, f"meta{idx}", (ml + 6, mt + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2)
                        cv2.rectangle(debug_img, (cl, ct), (cr, cb), (0, 255, 0), 1)
                    if active_card:
                        l, t, r, b = active_card.rect
                        cv2.rectangle(debug_img, (l, t), (r, b), (0, 255, 0), 2)
                        cv2.putText(debug_img, "ACTIVE", (l + 6, max(0, t - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                        
                    os.makedirs(debug_folder, exist_ok=True)
                    cv2.imwrite(os.path.join(debug_folder, f"layout_{ts}.png"), debug_img)
            
            keywords = config_loader.get("keywords", [])
            found_post = None
            candidates = []
            
            # Check posts one by one
            for post in posts:
                title_crop = image.crop(post.title_rect)
                ocr = vision_engine.extract_text_with_confidence(title_crop)
                post_matched = match_keywords(
                    ocr,
                    keywords,
                    min_avg_conf=min_ocr_avg_conf,
                    min_token_conf=min_ocr_token_conf,
                    min_cjk_ratio=min_ocr_cjk_ratio,
                )

                title_text = ocr.get("text", "")
                sig_img = signature_from_image(title_crop)
                sig_text = signature_from_text(title_text)
                sig = sig_img or sig_text
                if processed_store.seen(sig_img) or processed_store.seen(sig_text) or processed_store.seen(sig):
                    continue

                complete = False
                try:
                    complete = post.is_complete(content_rect)
                except Exception:
                    complete = False

                if complete:
                    candidates.append({"card": post, "ocr": ocr, "sig": sig, "matched": post_matched})

                if post_matched and complete and found_post is None:
                    post_key = _confirm_key(sig, title_text)
                    logger.info(
                        f"Found keywords {post_matched} in post: {post_key} (avg_conf={ocr.get('avg_conf', 0):.1f}, cjk_ratio={ocr.get('cjk_ratio', 0):.3f})"
                    )
                    found_post = {
                        "card": post,
                        "ocr": ocr,
                        "key": post_key,
                        "matched": post_matched,
                        "sig": sig,
                        "sig_img": sig_img,
                        "sig_text": sig_text,
                    }
            
            # Fallback for full text (if no posts detected)
            if not found_post:
                search_img = image
                ox, oy = 0, 0
                if content_rect:
                    try:
                        search_img = image.crop(content_rect)
                        ox, oy = int(content_rect[0]), int(content_rect[1])
                    except Exception:
                        search_img = image
                        ox, oy = 0, 0

                fallback_pt = None
                fallback_kw = None
                for k in keywords or []:
                    pt = vision_engine.find_text_location(search_img, k)
                    if pt:
                        fallback_pt = (int(pt[0]) + ox, int(pt[1]) + oy)
                        fallback_kw = str(k)
                        break
                if not fallback_pt and keywords:
                    pt = vision_engine.find_keyword_click_point(search_img, keywords)
                    if pt:
                        fallback_pt = (int(pt[0]) + ox, int(pt[1]) + oy)

                if fallback_pt:
                    qx = (fallback_pt[0] // 10) * 10
                    qy = (fallback_pt[1] // 10) * 10
                    post_key = f"pt_{qx}_{qy}"
                    if debug_log_path:
                        with open(debug_log_path, "a", encoding="utf-8") as f:
                            f.write(f"fallback_click_pt={fallback_pt}\n")
                            f.write(f"fallback_kw={fallback_kw}\n")
                    found_post = {
                        "card": None,
                        "ocr": {"text": "", "avg_conf": 0.0, "tokens": [], "cjk_ratio": 0.0},
                        "key": post_key,
                        "matched": [fallback_kw] if fallback_kw else [],
                        "sig": "",
                        "sig_img": "",
                        "sig_text": "",
                        "click_pt": fallback_pt,
                    }

            last_action = "none"
            
            if found_post and not open_on_match:
                logger.info("Found matched post but open_on_match=false. Skipping open.")
                found_post = None

            if found_post:
                click_pt = found_post.get("click_pt")
                if click_pt:
                    cx, cy = int(click_pt[0]), int(click_pt[1])
                else:
                    card = found_post["card"]
                    cl, ct, cr, cb = card.click_rect
                    if (cr - cl) * (cb - ct) < 2000:
                        if debug_log_path:
                            with open(debug_log_path, "a", encoding="utf-8") as f:
                                f.write("skip_open_reason=click_rect_too_small\n")
                        found_post = None
                    else:
                        cx = (cl + cr) // 2
                        cy = (ct + cb) // 2

            if not found_post:
                logger.info("No keywords found in any posts. Scrolling...")
                if debug_log_path:
                    with open(debug_log_path, "a", encoding="utf-8") as f:
                        f.write("skip_open_reason=no_match\n")
                if next_scroll_mode == "wheel":
                    interaction.scroll_down_wheel()
                else:
                    interaction.scroll_down(region=content_rect)
                last_action = "scroll"
                last_action_ts = time.monotonic()
                needs_reanalyze = True
                list_stable_frames = 0
                time.sleep(0.4)
                continue

            skip_reason = None
            now_mono = time.monotonic()
            if now_mono < skip_open_until:
                skip_reason = "startup_grace"
            elif match_confirm_frames > 1:
                key = (found_post.get("key") or "").strip()
                pending_key, pending_count, ready = update_confirm(
                    pending_key, pending_count, key, match_confirm_frames
                )
                if not ready:
                    if not key:
                        skip_reason = "empty_key"
                    else:
                        skip_reason = f"confirm_{pending_count}/{match_confirm_frames}"

            is_safe = True
            if layout_info:
                header = layout_info["safe_area"]["header"]
                footer = layout_info["safe_area"]["footer"]
                if _rect_contains(header, cx, cy) or _rect_contains(footer, cx, cy):
                    logger.warning(f"Click point ({cx},{cy}) is in unsafe area. Skipping.")
                    is_safe = False

            if skip_reason:
                logger.info(f"Skip open: {skip_reason}")
                if debug_log_path:
                    with open(debug_log_path, "a", encoding="utf-8") as f:
                        f.write(f"skip_open_reason={skip_reason}\n")
                        f.write(f"pending_key={pending_key}\n")
                        f.write(f"pending_count={pending_count}\n")
                time.sleep(0.2)
                continue

            if not is_safe:
                if debug_log_path:
                    with open(debug_log_path, "a", encoding="utf-8") as f:
                        f.write("skip_open_reason=unsafe_area\n")
                if next_scroll_mode == "wheel":
                    interaction.scroll_down_wheel()
                else:
                    interaction.scroll_down(region=content_rect)
                last_action = "scroll"
                last_action_ts = time.monotonic()
                needs_reanalyze = True
                list_stable_frames = 0
                time.sleep(0.2)
                continue

            visited_posts.add(found_post["key"])
            processed_store.mark(found_post.get("sig"))
            processed_store.mark(found_post.get("sig_img"))
            processed_store.mark(found_post.get("sig_text"))
            processed_store.save()

            open_x, open_y = cx, cy
            forbidden = None
            if layout_info:
                forbidden = [layout_info["safe_area"]["header"], layout_info["safe_area"]["footer"]]
            interaction.click(open_x, open_y, safe_check=True, forbidden_rects=forbidden)
            last_action = "open"
            last_action_ts = time.monotonic()
            time.sleep(float(config_loader.get("open_wait_seconds", 1.2)))

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

            title = _extract_title(page_texts[0] if page_texts else "") or _extract_title(
                found_post["ocr"].get("text", "")
            )
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
                "clicked": {"x": open_x, "y": open_y},
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
                try:
                    cr = win32gui.GetClientRect(getattr(interaction, "hwnd", 0))
                    client_w = int(cr[2])
                    client_h = int(cr[3])
                except Exception:
                    if before_image is not None:
                        client_w, client_h = before_image.size
                    else:
                        client_w, client_h = (0, 0)
                back_x_ratio = float(config_loader.get("back_click_x_ratio", 0.08))
                back_y_ratio = float(config_loader.get("back_click_y_ratio", 0.08))
                back_x = max(0, min(client_w - 1, int(client_w * back_x_ratio)))
                back_y = max(0, min(client_h - 1, int(client_h * back_y_ratio)))
                interaction.click(back_x, back_y)
            time.sleep(float(config_loader.get("back_wait_seconds", 1.0)))
            time.sleep(2)
            continue

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
