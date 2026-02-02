def test_confirm_key_prefers_sig():
    try:
        from src.main import _confirm_key
    except Exception:
        import pytest

        pytest.skip("src.main is not importable in this environment")

    assert _confirm_key("abc" * 20, "TITLE") == ("abc" * 20)[:12]


def test_confirm_key_falls_back_to_title_text():
    try:
        from src.main import _confirm_key
    except Exception:
        import pytest

        pytest.skip("src.main is not importable in this environment")

    assert _confirm_key("", "美团 大模型") == "美团大模型"
