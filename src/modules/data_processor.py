import json
import os
from datetime import datetime, timedelta
import re

class DataProcessor:
    def __init__(self, logger, output_config):
        self.logger = logger
        self.config = output_config
        self.output_folder = self.config.get("folder", "result")
        
        # Ensure output directory exists
        if not os.path.exists(self.output_folder):
            os.makedirs(self.output_folder)

    def parse_time(self, time_str, now=None):
        if not time_str:
            return ""
        if now is None:
            now = datetime.now()

        s = str(time_str).strip()
        s = re.sub(r"\s+", " ", s)
        s = s.replace("：", ":").replace("／", "/").replace("－", "-").replace("—", "-").replace("–", "-")

        def _format(dt):
            return dt.strftime("%Y-%m-%d %H:%M:%S")

        def _parse_hhmm(text):
            m = re.search(r"(\d{1,2})\s*:\s*(\d{1,2})", text)
            if not m:
                return None
            hh = int(m.group(1))
            mm = int(m.group(2))
            if not (0 <= hh <= 23 and 0 <= mm <= 59):
                return None
            return hh, mm

        try:
            if re.search(r"刚刚|刚才|现在", s):
                return _format(now)

            m = re.search(r"(\d+)\s*秒(钟)?前", s)
            if m:
                seconds = int(m.group(1))
                return _format(now - timedelta(seconds=seconds))

            m = re.search(r"(\d+)\s*分钟?前", s)
            if m:
                minutes = int(m.group(1))
                return _format(now - timedelta(minutes=minutes))

            m = re.search(r"(\d+)\s*小时(钟)?前", s)
            if m:
                hours = int(m.group(1))
                return _format(now - timedelta(hours=hours))

            m = re.search(r"(\d+)\s*天前", s)
            if m:
                days = int(m.group(1))
                return _format(now - timedelta(days=days))

            if "昨天" in s:
                hhmm = _parse_hhmm(s)
                base = now - timedelta(days=1)
                if hhmm:
                    hh, mm = hhmm
                    base = base.replace(hour=hh, minute=mm, second=0, microsecond=0)
                else:
                    base = base.replace(hour=0, minute=0, second=0, microsecond=0)
                return _format(base)

            if "前天" in s:
                hhmm = _parse_hhmm(s)
                base = now - timedelta(days=2)
                if hhmm:
                    hh, mm = hhmm
                    base = base.replace(hour=hh, minute=mm, second=0, microsecond=0)
                else:
                    base = base.replace(hour=0, minute=0, second=0, microsecond=0)
                return _format(base)

            m = re.search(
                r"(\d{4})\s*[-/.年]\s*(\d{1,2})\s*[-/.月]\s*(\d{1,2})\s*(日)?",
                s,
            )
            if m:
                year = int(m.group(1))
                month = int(m.group(2))
                day = int(m.group(3))
                hhmm = _parse_hhmm(s)
                if hhmm:
                    hh, mm = hhmm
                    dt = datetime(year, month, day, hh, mm, 0)
                else:
                    dt = datetime(year, month, day, 0, 0, 0)
                return _format(dt)

            m = re.search(r"(\d{1,2})\s*[-/.]\s*(\d{1,2})", s)
            if not m:
                m = re.search(r"(?:\b|于)\s*(\d{1,2})\s+(\d{1,2})(?:\b|日)?", s)
            if m:
                month = int(m.group(1))
                day = int(m.group(2))
                year = now.year
                hhmm = _parse_hhmm(s)
                if hhmm:
                    hh, mm = hhmm
                    dt = datetime(year, month, day, hh, mm, 0)
                else:
                    dt = datetime(year, month, day, 0, 0, 0)

                if dt > now + timedelta(days=1):
                    dt = dt.replace(year=year - 1)
                return _format(dt)

            hhmm = _parse_hhmm(s)
            if hhmm:
                hh, mm = hhmm
                dt = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
                return _format(dt)

            return s
        except Exception:
            return _format(now)

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
