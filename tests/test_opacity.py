from src.utils.opacity import percent_to_alpha


def test_percent_to_alpha_clamps():
    assert percent_to_alpha(-1) == 0
    assert percent_to_alpha(0) == 0
    assert percent_to_alpha(100) == 255
    assert percent_to_alpha(101) == 255


def test_percent_to_alpha_common_values():
    assert percent_to_alpha(15) == 38
    assert percent_to_alpha(80) == 204
