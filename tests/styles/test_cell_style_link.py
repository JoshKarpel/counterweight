import pytest

from counterweight.output import HYPERLINK_END, hyperlink, paint_to_str, sgr_from_cell_style
from counterweight.paint import Cell, Paint
from counterweight.styles import CellStyle
from counterweight.styles.styles import resolve_cell_style


@pytest.mark.parametrize(
    "link",
    [
        "https://example.com/",
        "https://example.com/a%20b?q=1;r=2#frag",
        "mailto:someone@example.com",
        "file:///tmp/x.txt",
    ],
)
def test_printable_ascii_link_is_accepted(link: str) -> None:
    assert CellStyle(link=link).link == link


@pytest.mark.parametrize(
    "link",
    [
        "",
        "https://example.com/\x1b]8;;evil\x1b\\",
        "https://example.com/\x07",
        "https://example.com/\n",
        "https://example.com/\x7f",
        "https://example.com/é",
    ],
)
def test_link_that_could_break_out_of_its_escape_sequence_is_rejected(link: str) -> None:
    with pytest.raises(ValueError, match="printable ASCII"):
        CellStyle(link=link)


def test_none_link_unsets_an_inherited_link() -> None:
    assert resolve_cell_style(CellStyle(link="https://example.com/") | CellStyle(link=None)).link is None


def test_hash_depends_on_link() -> None:
    assert hash(CellStyle(link="https://example.com/a")) != hash(CellStyle(link="https://example.com/b"))


def test_ansi_text_wraps_each_linked_cell_in_its_hyperlink() -> None:
    linked = resolve_cell_style(CellStyle(link="https://example.com/"))
    plain = resolve_cell_style(CellStyle())
    paint = Paint(2, 1, [Cell("a", linked), Cell("b", plain)])

    assert paint_to_str(paint) == (
        f"{sgr_from_cell_style(linked)}{hyperlink('https://example.com/')}a{HYPERLINK_END}\x1b[0m"
        f"{sgr_from_cell_style(plain)}b\x1b[0m"
    )
