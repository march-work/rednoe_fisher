import json
import os
from pathlib import Path

class ConfigLoader:
    def __init__(self, config_path="config/config.json"):
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self):
        path = Path(self.config_path)
        if not path.exists():
            # Fallback to absolute path if running from src
            root_dir = Path(__file__).parent.parent.parent
            path = root_dir / self.config_path
            
        if not path.exists():
            raise FileNotFoundError(f"Config file not found at {self.config_path}")

        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def get(self, key, default=None):
        return self.config.get(key, default)

    def get_scroll_config(self):
        return self.config.get("scroll_config", {})

    def get_ocr_config(self):
        return self.config.get("ocr_config", {})

    def get_output_config(self):
        return self.config.get("output_config", {})

    def get_layout_config(self):
        layout = self.config.get("layout_config")
        if isinstance(layout, dict):
            return layout
        keys = [
            "meta_ratio",
            "meta_min_h",
            "meta_max_h",
            "meta_boundary_search_px",
            "title_ratio",
            "title_padding_ratio",
            "title_min_h",
            "image_min_h",
            "title_white_ratio_thr",
            "title_white_run",
            "title_row_dark_frac",
            "title_line_h",
            "title_line_ratio",
            "title_line_h_min",
            "title_line_h_max",
            "title_pad_y",
            "title_text_dark_frac_min",
        ]
        out = {}
        for k in keys:
            if k in self.config:
                out[k] = self.config.get(k)
        return out
