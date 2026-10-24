import pytest

from counterweight.styles._styles import DEFAULT_PALETTE
from counterweight.styles._styles import TERMINAL_DEFAULT
from counterweight.styles._styles import AnyColor
from counterweight.styles._styles import Color
from counterweight.styles._styles import IndexedColor
from counterweight.styles._styles import TerminalDefault
from counterweight.styles._styles import palette
from counterweight.styles._styles import rgb_of


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


@pytest.mark.parametrize("index", [-1, 256])
def test_an_indexed_color_outside_the_palette_raises(index: int) -> None:
    with pytest.raises(ValueError, match=f"from 0 to 255, not {index}"):
        IndexedColor(index)


@pytest.mark.parametrize("index", [0, 255])
def test_an_indexed_color_can_be_any_palette_entry(index: int) -> None:
    assert IndexedColor(index).index == index


def test_every_terminal_default_is_equal() -> None:
    assert TerminalDefault() == TERMINAL_DEFAULT


ANSI = tuple(Color(index, 100, 200) for index in range(16))


@pytest.mark.parametrize(
    ("index", "expected"),
    [
        (0, Color(0, 100, 200)),
        (15, Color(15, 100, 200)),
        (16, Color(0, 0, 0)),
        (17, Color(0, 0, 95)),
        (22, Color(0, 95, 0)),
        (52, Color(95, 0, 0)),
        (196, Color(255, 0, 0)),
        (231, Color(255, 255, 255)),
        (232, Color(8, 8, 8)),
        (233, Color(18, 18, 18)),
        (255, Color(238, 238, 238)),
    ],
)
def test_a_palette_is_its_ansi_colors_then_xterms_color_cube_then_its_grays(index: int, expected: Color) -> None:
    assert palette(ANSI)[index] == expected


def test_a_palette_has_256_colors() -> None:
    assert len(palette(ANSI)) == 256


@pytest.mark.parametrize(
    ("color", "expected"),
    [
        (Color(1, 2, 3), Color(1, 2, 3)),
        (IndexedColor(1), DEFAULT_PALETTE[1]),
        (IndexedColor(200), DEFAULT_PALETTE[200]),
        (TERMINAL_DEFAULT, Color(9, 8, 7)),
    ],
)
def test_rgb_of_draws_terminal_colors_in_the_default_palette_and_the_given_default(
    color: AnyColor, expected: Color
) -> None:
    assert rgb_of(color, Color(9, 8, 7)) == expected
