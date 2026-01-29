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
