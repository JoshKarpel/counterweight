import pytest

from counterweight.output import HYPERLINK_END
from counterweight.output import hyperlink
from counterweight.output import paint_to_str
from counterweight.output import sgr_from_cell_style
from counterweight.paint import Cell
from counterweight.paint import Paint
from counterweight.styles import CellStyle
from counterweight.styles.styles import resolve_cell_style


@pytest.mark.parametrize(
    "link",
    [
        "https://example.com/",
        "https://example.com/a%20b?q=1;r=2#frag",
        "mailto:someone@example.com",
        "file:///tmp/x.txt",
        "file:///tmp/a b.txt",
        "https://example.com/~user",
    ],
    ids=["https", "escaped", "mailto", "file", "space", "tilde"],
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


A = resolve_cell_style(CellStyle(link="https://example.com/a"))
B = resolve_cell_style(CellStyle(link="https://example.com/b"))
PLAIN = resolve_cell_style(CellStyle())


def styled(cell: Cell) -> str:
    return f"{sgr_from_cell_style(cell.style)}{cell.grapheme}\x1b[0m"


def test_ansi_text_wraps_a_run_of_cells_with_the_same_link_in_one_hyperlink() -> None:
    cells = [Cell("x", A), Cell("y", A), Cell("z", PLAIN)]

    assert paint_to_str(Paint(3, 1, cells)) == (
        f"{hyperlink(A.link)}{styled(cells[0])}{styled(cells[1])}{HYPERLINK_END}{styled(cells[2])}"
    )


def test_ansi_text_switches_directly_between_adjacent_links() -> None:
    cells = [Cell("x", A), Cell("y", B)]

    assert paint_to_str(Paint(2, 1, cells)) == (
        f"{hyperlink(A.link)}{styled(cells[0])}{hyperlink(B.link)}{styled(cells[1])}{HYPERLINK_END}"
    )


def test_ansi_text_closes_a_hyperlink_at_the_end_of_each_row() -> None:
    cells = [Cell("x", A), Cell("y", A)]

    assert paint_to_str(Paint(1, 2, cells)) == (
        f"{hyperlink(A.link)}{styled(cells[0])}{HYPERLINK_END}\n{hyperlink(A.link)}{styled(cells[1])}{HYPERLINK_END}"
    )
