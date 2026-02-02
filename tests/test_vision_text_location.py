import logging

import pytesseract
from PIL import Image

from src.modules.vision_engine import VisionEngine


def test_find_text_location_returns_center(monkeypatch):
    logger = logging.getLogger("test")
    ve = VisionEngine(logger, {"language": "chi_sim", "psm": 6, "scale": 2.0}, setup_tesseract=False)
    image = Image.new("RGB", (100, 60), color=(255, 255, 255))

    def fake_image_to_data(*args, **kwargs):
        return {
            "text": ["大", "模型"],
            "conf": ["80", "85"],
            "left": [20, 30],
            "top": [10, 10],
            "width": [10, 20],
            "height": [10, 10],
            "block_num": [1, 1],
            "par_num": [1, 1],
            "line_num": [1, 1],
        }

    monkeypatch.setattr(pytesseract, "image_to_data", fake_image_to_data)

    pt = ve.find_text_location(image, "大模型")
    assert pt == (17, 7)


def test_find_text_location_prefers_higher_conf(monkeypatch):
    logger = logging.getLogger("test")
    ve = VisionEngine(logger, {"language": "chi_sim", "psm": 6, "scale": 1.0}, setup_tesseract=False)
    image = Image.new("RGB", (200, 80), color=(255, 255, 255))

    def fake_image_to_data(*args, **kwargs):
        return {
            "text": ["大", "模型", "大", "模型"],
            "conf": ["30", "30", "90", "90"],
            "left": [10, 30, 110, 130],
            "top": [10, 10, 40, 40],
            "width": [10, 20, 10, 20],
            "height": [10, 10, 10, 10],
            "block_num": [1, 1, 1, 1],
            "par_num": [1, 1, 1, 1],
            "line_num": [1, 1, 2, 2],
        }

    monkeypatch.setattr(pytesseract, "image_to_data", fake_image_to_data)

    pt = ve.find_text_location(image, "大模型")
    assert pt == (130, 45)
