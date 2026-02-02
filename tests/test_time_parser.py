import logging
from datetime import datetime

from src.modules.data_processor import DataProcessor


def _dp(tmp_path):
    logger = logging.getLogger("test")
    return DataProcessor(logger, {"folder": str(tmp_path), "filename_pattern": "{keyword}_{timestamp}"})


def test_parse_time_relative_minutes(tmp_path):
    dp = _dp(tmp_path)
    now = datetime(2026, 2, 2, 12, 0, 0)
    assert dp.parse_time("15分钟前", now=now) == "2026-02-02 11:45:00"


def test_parse_time_relative_hours(tmp_path):
    dp = _dp(tmp_path)
    now = datetime(2026, 2, 2, 12, 0, 0)
    assert dp.parse_time("2小时前", now=now) == "2026-02-02 10:00:00"


def test_parse_time_yesterday_with_time(tmp_path):
    dp = _dp(tmp_path)
    now = datetime(2026, 2, 2, 12, 0, 0)
    assert dp.parse_time("昨天 18:30", now=now) == "2026-02-01 18:30:00"


def test_parse_time_absolute_ymd(tmp_path):
    dp = _dp(tmp_path)
    now = datetime(2026, 2, 2, 12, 0, 0)
    assert dp.parse_time("2026-01-22", now=now) == "2026-01-22 00:00:00"


def test_parse_time_md_with_dash(tmp_path):
    dp = _dp(tmp_path)
    now = datetime(2026, 2, 2, 12, 0, 0)
    assert dp.parse_time("01-22", now=now) == "2026-01-22 00:00:00"


def test_parse_time_md_with_space(tmp_path):
    dp = _dp(tmp_path)
    now = datetime(2026, 2, 2, 12, 0, 0)
    assert dp.parse_time("01 22", now=now) == "2026-01-22 00:00:00"


def test_parse_time_time_only(tmp_path):
    dp = _dp(tmp_path)
    now = datetime(2026, 2, 2, 12, 0, 0)
    assert dp.parse_time("23:59", now=now) == "2026-02-02 23:59:00"


def test_parse_time_md_year_rollover(tmp_path):
    dp = _dp(tmp_path)
    now = datetime(2026, 1, 1, 0, 10, 0)
    assert dp.parse_time("12-31", now=now) == "2025-12-31 00:00:00"
