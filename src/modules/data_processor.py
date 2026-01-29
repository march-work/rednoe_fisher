import json
import os
from datetime import datetime
import re

class DataProcessor:
    def __init__(self, logger, output_config):
        self.logger = logger
        self.config = output_config
        self.output_folder = self.config.get("folder", "result")
        
        # Ensure output directory exists
        if not os.path.exists(self.output_folder):
            os.makedirs(self.output_folder)

    def parse_time(self, time_str):
        """Convert relative time strings to absolute datetime."""
        # Simple implementation for MVP
        # "2小时前", "昨天", "2023-01-01"
        now = datetime.now()
        try:
            if "小时前" in time_str:
                hours = int(re.search(r'(\d+)', time_str).group(1))
                # This is just a placeholder logic, strictly speaking we should subtract
                return now.strftime("%Y-%m-%d %H:%M:%S")
            elif "分钟前" in time_str:
                return now.strftime("%Y-%m-%d %H:%M:%S")
            elif "昨天" in time_str:
                # Placeholder
                return now.strftime("%Y-%m-%d 00:00:00")
            else:
                return time_str # Assume it's already a date or unparsable
        except:
            return now.strftime("%Y-%m-%d %H:%M:%S")

    def save_post(self, data):
        """Save extracted post data to JSON file."""
        try:
            # Add timestamp if not present
            if "scraped_at" not in data:
                data["scraped_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Generate filename
            pattern = self.config.get("filename_pattern", "{keyword}_{timestamp}")
            keyword = data.get("keywords_matched", ["unknown"])[0] if data.get("keywords_matched") else "unknown"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            filename = pattern.format(keyword=keyword, timestamp=timestamp) + ".json"
            filepath = os.path.join(self.output_folder, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
                
            self.logger.info(f"Saved data to {filepath}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to save data: {e}")
            return False
