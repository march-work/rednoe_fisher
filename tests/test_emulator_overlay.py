import time


def test_emulator_overlay_text_fallback(monkeypatch):
    try:
        import win32gui  # type: ignore
    except Exception:
        import pytest

        pytest.skip("pywin32 is not available")

    from src.utils.emulator_overlay import EmulatorOverlay

    monkeypatch.delattr(win32gui, "TextOut", raising=False)

    overlay = EmulatorOverlay(mask_alpha=38, fg_alpha=204)
    overlay.start()
    overlay.set_target_rect((0, 0, 120, 120))
    overlay.set_render_state(
        {
            "mask": True,
            "content_rect": (0, 0, 120, 120),
            "active_rect": (10, 10, 110, 60),
            "cards": [
                {
                    "rect": (10, 10, 110, 110),
                    "title_rect": (12, 12, 108, 28),
                    "click_rect": (10, 10, 110, 110),
                    "label": "Post-1",
                }
            ],
        }
    )

    time.sleep(0.2)
    overlay.stop()
    overlay.thread.join(timeout=2)
    assert not overlay.thread.is_alive()
