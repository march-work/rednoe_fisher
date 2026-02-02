import cv2
import numpy as np
from PIL import Image

class LayoutAnalyzer:
    """
    Analyzes the layout of the XiaoHongShu app page to identify safe areas
    and segment post cards in a waterfall flow.
    """
    def __init__(self, config=None):
        self.config = config or {}
        # Default safe area ratios (can be overridden by config)
        self.header_ratio = self.config.get("header_ratio", 0.15)  # Top 15% for nav bar
        self.footer_ratio = self.config.get("footer_ratio", 0.10)  # Bottom 10% for tab bar
        
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
        mid_x = content_w // 2
        col_width = mid_x
        
        left_col_img = content_np[:, :mid_x]
        right_col_img = content_np[:, mid_x:]
        
        posts = []
        
        # Process left column
        left_rects = self._find_cards_in_column(left_col_img)
        for r in left_rects:
            rx, ry, rw, rh = r
            # Map back to full screen coordinates
            global_rect = (left + rx, top + ry, rw, rh)
            crop = image.crop((global_rect[0], global_rect[1], global_rect[0]+rw, global_rect[1]+rh))
            posts.append({
                "rect": global_rect,
                "image": crop,
                "column": "left"
            })
            
        # Process right column
        right_rects = self._find_cards_in_column(right_col_img)
        for r in right_rects:
            rx, ry, rw, rh = r
            # Map back to full screen coordinates (offset x by mid_x)
            global_rect = (left + mid_x + rx, top + ry, rw, rh)
            crop = image.crop((global_rect[0], global_rect[1], global_rect[0]+rw, global_rect[1]+rh))
            posts.append({
                "rect": global_rect,
                "image": crop,
                "column": "right"
            })
            
        # Sort by vertical position (top to bottom)
        posts.sort(key=lambda p: p["rect"][1])
        
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
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 15))
        dilated = cv2.dilate(edges, kernel, iterations=2)
        
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
            
        return cards
