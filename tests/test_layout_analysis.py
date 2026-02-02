import pytest
import numpy as np
import cv2
from PIL import Image
from src.modules.layout_analysis import LayoutAnalyzer

class TestLayoutAnalyzer:
    @pytest.fixture
    def analyzer(self):
        return LayoutAnalyzer()

    def test_detect_safe_area(self, analyzer):
        width, height = 1080, 1920
        header, footer, content = analyzer.detect_safe_area(width, height)
        
        # Default ratios: header 0.15, footer 0.10
        expected_header_h = int(1920 * 0.15)
        expected_footer_h = int(1920 * 0.10)
        
        assert header == (0, 0, 1080, expected_header_h)
        assert footer == (0, 1920 - expected_footer_h, 1080, 1920)
        assert content == (0, expected_header_h, 1080, 1920 - expected_footer_h)

    def test_segment_waterfall_flow(self, analyzer):
        # Create a synthetic image with two columns of rectangles
        width, height = 400, 800
        # Safe area
        header_h = 100
        footer_h = 100
        content_rect = (0, header_h, 400, 800 - footer_h)
        
        # Create blank white image
        img_np = np.ones((height, width, 3), dtype=np.uint8) * 255
        
        # Draw some "cards" (black rectangles on white background)
        # We need edges for Canny detection.
        # Let's draw gray rectangles with black borders
        
        # Left column (0-200)
        # Card 1 - Make them separate enough
        cv2.rectangle(img_np, (20, 120), (180, 220), (100, 100, 100), -1)
        cv2.rectangle(img_np, (20, 120), (180, 220), (0, 0, 0), 2)
        
        # Card 2
        cv2.rectangle(img_np, (20, 320), (180, 500), (100, 100, 100), -1)
        cv2.rectangle(img_np, (20, 320), (180, 500), (0, 0, 0), 2)
        
        # Right column (200-400)
        # Card 3 (offset y)
        cv2.rectangle(img_np, (220, 150), (380, 350), (100, 100, 100), -1)
        cv2.rectangle(img_np, (220, 150), (380, 350), (0, 0, 0), 2)
        
        pil_img = Image.fromarray(img_np)
        
        posts = analyzer.segment_waterfall_flow(pil_img, content_rect)
        
        # We expect 3 posts
        assert len(posts) == 3
        
        # Verify columns
        left_posts = [p for p in posts if p["column"] == "left"]
        right_posts = [p for p in posts if p["column"] == "right"]
        
        assert len(left_posts) == 2
        assert len(right_posts) == 1
        
        # Verify sorting (top to bottom)
        assert left_posts[0]["rect"][1] < left_posts[1]["rect"][1]
        
        # Verify coordinates (approximate)
        # Left Card 1
        r1 = left_posts[0]["rect"]
        assert 10 <= r1[0] <= 30
        # The rect might be slightly larger due to dilation and border width
        # rect y is around 120, minus some dilation padding
        assert 100 <= r1[1] <= 130
