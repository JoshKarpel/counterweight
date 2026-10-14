import pytest

from counterweight.styles.styles import Color


@pytest.mark.parametrize("hex", ["#1a2b3c", "1a2b3c"])
def test_from_hex_reads_six_digits(hex: str) -> None:
    assert Color.from_hex(hex) == Color(0x1A, 0x2B, 0x3C)


@pytest.mark.parametrize("hex", ["#a2c", "a2c"])
def test_from_hex_reads_the_three_digit_shorthand(hex: str) -> None:
    assert Color.from_hex(hex) == Color(0xAA, 0x22, 0xCC)


@pytest.mark.parametrize("hex", ["#1a2b", "#1a2b3c4d", ""])
def test_from_hex_rejects_other_numbers_of_digits(hex: str) -> None:
    with pytest.raises(ValueError, match="3 or 6 digits"):
        Color.from_hex(hex)


def test_blend_moves_each_channel_alpha_of_the_way_to_the_other_color() -> None:
    assert Color(10, 100, 200).blend(Color(250, 20, 60), alpha=0.25) == Color(70, 80, 165)


def test_blend_truncates_fractional_channels() -> None:
    assert Color(0, 0, 0).blend(Color(3, 5, 7), alpha=0.5) == Color(1, 2, 3)
