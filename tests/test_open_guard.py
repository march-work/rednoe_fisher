from src.utils.open_guard import update_confirm


def test_update_confirm_empty_key_not_ready():
    k, c, ready = update_confirm(None, 0, "", 2)
    assert ready is False
    assert c == 0


def test_update_confirm_frames_1_ready():
    k, c, ready = update_confirm(None, 0, "abc", 1)
    assert ready is True
    assert k == "abc"
    assert c == 1


def test_update_confirm_requires_two_hits():
    k, c, ready = update_confirm(None, 0, "p", 2)
    assert ready is False
    assert (k, c) == ("p", 1)

    k, c, ready = update_confirm(k, c, "p", 2)
    assert ready is True
    assert (k, c) == ("p", 2)


def test_update_confirm_resets_on_new_key():
    k, c, ready = update_confirm(None, 0, "a", 2)
    assert ready is False
    assert (k, c) == ("a", 1)

    k, c, ready = update_confirm(k, c, "b", 2)
    assert ready is False
    assert (k, c) == ("b", 1)
