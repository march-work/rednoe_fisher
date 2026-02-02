import os

import pytest
from PIL import Image

from src.modules.layout_analysis import LayoutAnalyzer


@pytest.mark.skipif(not os.environ.get("FISHER_REGRESSION_IMAGE"), reason="no regression image")
def test_layout_regression_image_has_posts():
    path = os.environ["FISHER_REGRESSION_IMAGE"]
    img = Image.open(path)
    analyzer = LayoutAnalyzer()
    header, footer, content = analyzer.detect_safe_area(*img.size)
    posts = analyzer.segment_waterfall_flow(img, content)
    assert len(posts) >= 2
