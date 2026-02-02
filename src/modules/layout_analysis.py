import cv2
import numpy as np
from PIL import Image

from src.modules.layout_models import PostCard

class LayoutAnalyzer:
    """
    Analyzes the layout of the XiaoHongShu app page to identify safe areas
    and segment post cards in a waterfall flow.
    """
    def __init__(self, config=None):
        self.config = config or {}
        self.header_ratio = float(self.config.get("header_ratio", 0.15))
        self.footer_ratio = float(self.config.get("footer_ratio", 0.10))
        self.title_ratio = float(self.config.get("title_ratio", 0.28))
        self.title_padding_ratio = float(self.config.get("title_padding_ratio", 0.06))
        self.column_split_ratio = float(self.config.get("column_split_ratio", 0.5))
        
    def detect_safe_area(self, width, height):
        """
        Calculate safe content area excluding header and footer.
        Returns: (header_rect, footer_rect, content_rect)
        Each rect is (left, top, right, bottom)
        """
        header_h = int(height * self.header_ratio)
        footer_h = int(height * self.footer_ratio)
        
        header_rect = (0, 0, width, header_h)
        footer_rect = (0, height - footer_h, width, height)
        content_rect = (0, header_h, width, height - footer_h)
        
        return header_rect, footer_rect, content_rect

    def segment_waterfall_flow(self, image, content_rect):
        """
        Segment the waterfall flow into individual post cards.
        Args:
            image: PIL Image of the full screen
            content_rect: (left, top, right, bottom) of the waterfall area
        Returns:
            List of dicts: [{"rect": (x,y,w,h), "image": crop_img, "column": "left|right"}]
        """
        left, top, right, bottom = content_rect
        content_w = right - left
        content_h = bottom - top
        
        # Crop content area
        content_img = image.crop(content_rect)
        content_np = np.array(content_img)
        
        # Split into left and right columns
        mid_x = int(content_w * self.column_split_ratio)
        col_width = mid_x
        
        left_col_img = content_np[:, :mid_x]
        right_col_img = content_np[:, mid_x:]
        
        posts: list[PostCard] = []

        def _intersect(a, b):
            al, at, ar, ab = a
            bl, bt, br, bb = b
            l2 = max(al, bl)
            t2 = max(at, bt)
            r2 = min(ar, br)
            b2 = min(ab, bb)
            if r2 <= l2 or b2 <= t2:
                return None
            return (l2, t2, r2, b2)

        def _split_card_parts(rect_abs):
            l, t, r, b = rect_abs
            rl, rt = int(l - left), int(t - top)
            rr, rb = int(r - left), int(b - top)
            if rb <= rt or rr <= rl:
                return None, None, None
            crop = content_np[max(0, rt) : max(0, rb), max(0, rl) : max(0, rr)]
            if crop.size == 0:
                return None, None, None
            h, w = crop.shape[:2]
            if h < 80 or w < 80:
                return None, None, None

            meta_ratio = float(self.config.get("meta_ratio", 0.12))
            meta_min_h = int(self.config.get("meta_min_h", 42))
            meta_max_h = int(self.config.get("meta_max_h", 72))
            title_min_h = int(self.config.get("title_min_h", 64))
            image_min_h = int(self.config.get("image_min_h", 90))
            meta_search_px = int(self.config.get("meta_boundary_search_px", 30))
            title_pad_y = int(self.config.get("title_pad_y", 10))
            title_line_h = self.config.get("title_line_h", None)
            title_line_ratio = self.config.get("title_line_ratio", None)
            title_line_h_min = int(self.config.get("title_line_h_min", 34))
            title_line_h_max = int(self.config.get("title_line_h_max", 64))
            title_text_dark_frac_min = float(self.config.get("title_text_dark_frac_min", 0.012))
            title_row_dark_frac = float(self.config.get("title_row_dark_frac", 0.015))

            gray = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
            try:
                _, bin_inv = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            except Exception:
                bin_inv = cv2.adaptiveThreshold(
                    gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 7
                )

            row_frac_all = np.mean(bin_inv > 0, axis=1).astype(np.float32)

            # Trim whitespace from top and bottom
            h_full = h
            valid_top = 0
            valid_bottom = h_full
            content_thr = 0.005

            for i in range(h_full):
                if row_frac_all[i] > content_thr:
                    valid_top = i
                    break
            
            for i in range(h_full - 1, -1, -1):
                if row_frac_all[i] > content_thr:
                    valid_bottom = i + 1
                    break
            
            if valid_bottom - valid_top < 40:
                valid_top = 0
                valid_bottom = h_full

            if valid_top > 0 or valid_bottom < h_full:
                bin_inv = bin_inv[valid_top:valid_bottom, :]
                row_frac_all = row_frac_all[valid_top:valid_bottom]
                t += valid_top
                h = valid_bottom - valid_top

            if row_frac_all.size >= 7:
                kernel = np.ones(7, dtype=np.float32) / 7.0
                row_frac_all = np.convolve(row_frac_all, kernel, mode="same")

            meta_h = int(round(h * meta_ratio))
            meta_h = max(meta_min_h, min(meta_max_h, meta_h))
            meta_h = min(meta_h, max(20, h // 3))
            title_bottom_guess = h - meta_h
            if title_bottom_guess < title_min_h + 10:
                return None, None, None

            title_bottom = int(title_bottom_guess)
            if meta_search_px > 0 and row_frac_all.size > 0:
                lo = int(max(title_min_h + 10, h - meta_max_h - meta_search_px))
                hi = int(min(h - meta_min_h, title_bottom_guess + meta_search_px))
                if hi - lo >= 10:
                    window = row_frac_all[lo:hi]
                    try:
                        offset = int(np.argmin(window))
                        candidate = lo + offset
                        candidate = int(max(title_min_h + 10, min(candidate, h - meta_min_h)))
                        if candidate < h - 20 and candidate > 40:
                            title_bottom = candidate
                    except Exception:
                        title_bottom = int(title_bottom_guess)

            if title_line_h is None:
                if title_line_ratio is not None:
                    try:
                        title_line_h = int(round(float(title_line_ratio) * w))
                    except Exception:
                        title_line_h = None
                if title_line_h is None:
                    title_line_h = int(round(meta_h * 1.15))
            title_line_h = int(max(title_line_h_min, min(title_line_h_max, int(title_line_h))))

            title_h_1 = int(max(title_min_h, title_line_h + title_pad_y))
            title_h_2 = int(max(title_min_h, 2 * title_line_h + title_pad_y))
            title_h_2 = int(min(title_h_2, max(title_h_1, title_bottom - 10)))

            def _dark_frac(y0, y1):
                if y1 <= y0 + 2:
                    return 0.0, 0.0, 0.0
                band = bin_inv[int(y0) : int(y1), :]
                if band.size == 0:
                    return 0.0, 0.0, 0.0
                df = float(np.mean(band > 0))
                mid = int((y1 - y0) // 2)
                upper = band[:mid, :]
                lower = band[mid:, :]
                uf = float(np.mean(upper > 0)) if upper.size else 0.0
                lf = float(np.mean(lower > 0)) if lower.size else 0.0
                return df, uf, lf

            def _score_title(top, bottom, mode):
                df, uf, lf = _dark_frac(top, bottom)
                if df < title_text_dark_frac_min:
                    return -1e9
                if mode == 1:
                    return max(uf, lf) - 0.8 * min(uf, lf) + 0.2 * df
                return min(uf, lf) + 0.3 * df

            top1 = int(max(0, title_bottom - title_h_1))
            top2 = int(max(0, title_bottom - title_h_2))
            s1 = _score_title(top1, title_bottom, 1)
            s2 = _score_title(top2, title_bottom, 2)

            if s2 > s1:
                title_top = top2
            else:
                title_top = top1

            if title_bottom - title_top < title_min_h:
                title_top = int(max(0, title_bottom - title_min_h))

            if title_top < image_min_h:
                title_top = int(max(0, title_bottom - max(title_min_h, int(h * self.title_ratio))))
                title_top = int(min(title_top, title_bottom - title_min_h))
                df, _, _ = _dark_frac(title_top, title_bottom)
                if df < title_text_dark_frac_min:
                    title_top = int(max(0, title_bottom - title_h_2))
                    title_top = int(min(title_top, title_bottom - title_min_h))
                    df, _, _ = _dark_frac(title_top, title_bottom)
                    if df < title_text_dark_frac_min:
                        title_top = int(max(0, title_bottom - title_h_1))
                        title_top = int(min(title_top, title_bottom - title_min_h))

            pad = int(w * self.title_padding_ratio)
            title_rect = (l, t + title_top, r, t + title_bottom)
            meta_rect = (l, t + title_bottom, r, b)
            title_h = int(max(1, title_bottom - title_top))
            image_h = int(title_top)
            max_ratio = float(self.config.get("image_title_max_ratio", 5.0))
            image_rect = (l, t, r, t + title_top) if title_top >= image_min_h else None
            if image_rect and max_ratio > 0 and image_h > int(max_ratio * title_h):
                pass
            return image_rect, title_rect, meta_rect
        
        # Process left column
        left_rects = self._find_cards_in_column(left_col_img)
        for r in left_rects:
            rx, ry, rw, rh = r
            rect_abs = (left + rx, top + ry, left + rx + rw, top + ry + rh)
            click_rect = _intersect(rect_abs, content_rect) or rect_abs
            image_rect, title_rect, meta_rect = _split_card_parts(rect_abs)
            posts.append(
                PostCard(
                    rect=rect_abs,
                    image_rect=image_rect,
                    title_rect=title_rect or rect_abs,
                    meta_rect=meta_rect,
                    click_rect=click_rect,
                    column="left",
                )
            )
            
        # Process right column
        right_rects = self._find_cards_in_column(right_col_img)
        for r in right_rects:
            rx, ry, rw, rh = r
            rect_abs = (left + mid_x + rx, top + ry, left + mid_x + rx + rw, top + ry + rh)
            click_rect = _intersect(rect_abs, content_rect) or rect_abs
            image_rect, title_rect, meta_rect = _split_card_parts(rect_abs)
            posts.append(
                PostCard(
                    rect=rect_abs,
                    image_rect=image_rect,
                    title_rect=title_rect or rect_abs,
                    meta_rect=meta_rect,
                    click_rect=click_rect,
                    column="right",
                )
            )
            
        # Sort by vertical position (top to bottom)
        posts.sort(key=lambda p: p.rect[1])
        
        return posts

    def _find_cards_in_column(self, col_img_np):
        """
        Find card contours in a single column image.
        Returns list of (x, y, w, h) relative to the column image.
        """
        # 1. Preprocess
        img_cv = cv2.cvtColor(col_img_np, cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        # Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # 2. Edge Detection
        edges = cv2.Canny(blurred, 50, 150)
        
        # 3. Morphological Dilation
        # Use a vertical kernel to connect image and text
        # Kernel size is critical: (3, 10) means connect vertically more than horizontally
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 11))
        dilated = cv2.dilate(edges, kernel, iterations=1)
        
        # 4. Find Contours
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        cards = []
        img_h, img_w = col_img_np.shape[:2]
        min_area = (img_w * img_h) * 0.05 # Ignore blocks smaller than 5% of column
        
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            
            # Filter by area
            if w * h < min_area:
                continue
                
            # Filter by width (should occupy most of the column width)
            # A card usually takes up > 70% of the column width (considering margins)
            if w < img_w * 0.7:
                continue
                
            # Filter by aspect ratio (posts are usually taller than wide or square-ish)
            # But text-only posts might be short. Let's be lenient on height.
            if h < 50: # Minimum height in pixels
                continue
                
            cards.append((x, y, w, h))

        if not cards:
            return cards

        gap_min = int(self.config.get("column_split_gap_min", 14))
        min_piece_h = int(self.config.get("column_split_min_piece_h", 80))
        max_splits = int(self.config.get("column_split_max_splits", 2))
        edge_thr = float(self.config.get("column_split_edge_thr", 0.012))
        dark_thr = float(self.config.get("column_split_dark_thr", 0.018))
        white_thr = float(self.config.get("column_split_white_thr", 0.82))

        def _split_once(rx, ry, rw, rh):
            if rh < max(min_piece_h * 2, int(img_w * 1.2)):
                return [(rx, ry, rw, rh)]
            sub_edge = dilated[ry : ry + rh, rx : rx + rw]
            sub_gray = gray[ry : ry + rh, rx : rx + rw]
            if sub_edge.size == 0 or sub_gray.size == 0:
                return [(rx, ry, rw, rh)]
            proj_edge = np.mean(sub_edge > 0, axis=1).astype(np.float32)
            proj_dark = np.mean(sub_gray < 225, axis=1).astype(np.float32)
            proj_white = np.mean(sub_gray > 245, axis=1).astype(np.float32)
            if proj_edge.size >= 9:
                kernel2 = np.ones(9, dtype=np.float32) / 9.0
                proj_edge = np.convolve(proj_edge, kernel2, mode="same")
                proj_dark = np.convolve(proj_dark, kernel2, mode="same")
                proj_white = np.convolve(proj_white, kernel2, mode="same")
            mask = (proj_edge < edge_thr) & (proj_dark < dark_thr) & (proj_white > white_thr)
            segs = []
            start = None
            for i, on in enumerate(mask.tolist()):
                if on and start is None:
                    start = i
                elif (not on) and start is not None:
                    if i - start >= gap_min:
                        segs.append((start, i))
                    start = None
            if start is not None and len(mask) - start >= gap_min:
                segs.append((start, len(mask)))
            if not segs:
                return [(rx, ry, rw, rh)]

            best = None
            best_score = -1e18
            for s0, s1 in segs:
                split_rel = int((s0 + s1) // 2)
                top_h = split_rel
                bot_h = rh - split_rel
                if top_h < min_piece_h or bot_h < min_piece_h:
                    continue
                gap_edge = float(np.mean(proj_edge[s0:s1])) if s1 > s0 else 1.0
                gap_dark = float(np.mean(proj_dark[s0:s1])) if s1 > s0 else 1.0
                gap_white = float(np.mean(proj_white[s0:s1])) if s1 > s0 else 0.0
                balance = -abs(top_h - bot_h) / float(max(1, rh))
                score = (-gap_edge * 2.5) + (-gap_dark * 2.0) + (gap_white * 1.0) + balance
                if score > best_score:
                    best_score = score
                    best = split_rel
            if best is None:
                return [(rx, ry, rw, rh)]
            top = (rx, ry, rw, int(best))
            bot = (rx, ry + int(best), rw, int(rh - best))
            return [top, bot]

        def _split_recursive(rect, budget):
            if budget <= 0:
                return [rect]
            parts = _split_once(*rect)
            if len(parts) == 1:
                return [rect]
            out = []
            for p in parts:
                out.extend(_split_recursive(p, budget - 1))
            return out

        split_cards = []
        for rect in cards:
            split_cards.extend(_split_recursive(rect, max_splits))

        split_cards = [(x, y, w, h) for (x, y, w, h) in split_cards if h >= 50 and w >= img_w * 0.7]
        split_cards.sort(key=lambda r: r[1])
        return split_cards
