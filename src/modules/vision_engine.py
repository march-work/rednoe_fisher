import cv2
import numpy as np
import pytesseract
from PIL import Image, ImageGrab
import os

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

    def preprocess_image(self, image):
        """Convert PIL image to OpenCV format and preprocess for OCR."""
        # Convert PIL to OpenCV (RGB -> BGR)
        img_np = np.array(image)
        img_cv = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        
        # Gray scale
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        # Binary thresholding (optional, depends on UI contrast)
        # _, binary = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
        
        return gray

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

    def find_text_location(self, image, target_text):
        """Find location of specific text in image (not fully implemented in MVP)."""
        # This would require using image_to_data to get bounding boxes
        pass
