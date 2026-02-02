from src.utils.keyword_matcher import match_keywords


def test_match_keywords_rejects_low_avg_conf():
    ocr = {"text": "AI 大模型", "avg_conf": 10.0, "tokens": [{"text": "AI", "conf": 95}], "cjk_ratio": 0.5}
    assert match_keywords(ocr, ["AI"], min_avg_conf=55) == []


def test_match_keywords_short_ascii_requires_token_and_conf():
    ocr = {"text": "SOME RANDOM", "avg_conf": 80.0, "tokens": [{"text": "AI", "conf": 40}], "cjk_ratio": 0.0}
    assert match_keywords(ocr, ["AI"], min_token_conf=60) == []

    ocr2 = {"text": "SOME RANDOM", "avg_conf": 80.0, "tokens": [{"text": "AI", "conf": 90}], "cjk_ratio": 0.0}
    assert match_keywords(ocr2, ["AI"], min_token_conf=60) == ["AI"]


def test_match_keywords_long_keyword_uses_normalized_contains():
    ocr = {"text": "阶跃星辰 大模型 算法", "avg_conf": 80.0, "tokens": [], "cjk_ratio": 0.8}
    assert match_keywords(ocr, ["大模型"]) == ["大模型"]


def test_match_keywords_cjk_can_match_low_avg_conf():
    ocr = {"text": "美团大模型算法工程师", "avg_conf": 10.0, "tokens": [], "cjk_ratio": 0.6}
    assert match_keywords(ocr, ["大模型"], min_avg_conf=55, min_cjk_ratio=0.02) == ["大模型"]


def test_match_keywords_non_cjk_still_requires_avg_conf():
    ocr = {"text": "LLM", "avg_conf": 10.0, "tokens": [{"text": "LLM", "conf": 95}], "cjk_ratio": 0.0}
    assert match_keywords(ocr, ["LLM"], min_avg_conf=55) == []


def test_match_keywords_skips_empty_keywords():
    ocr = {"text": "AI", "avg_conf": 80.0, "tokens": [{"text": "AI", "conf": 90}], "cjk_ratio": 0.0}
    assert match_keywords(ocr, ["", None, "AI"]) == ["AI"]
