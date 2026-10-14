import pytest

from counterweight.output import Frame
from counterweight.paint import Cell
from counterweight.paint import Paint
from counterweight.paint import svg
from counterweight.paint import svg_text_style
from counterweight.styles.styles import CellStyle
from counterweight.styles.styles import Color
from counterweight.styles.styles import ResolvedCellStyle
from counterweight.styles.styles import resolve_cell_style


def style(foreground: str = "white", background: str = "black") -> ResolvedCellStyle:
    return resolve_cell_style(CellStyle(foreground=Color.from_name(foreground), background=Color.from_name(background)))


def test_svg_draws_background_runs_as_rectangles_and_skips_blank_cells_and_white_text() -> None:
    paint = Paint(
        width=3,
        height=2,
        cells=[
            Cell("a", style(foreground="red", background="blue")),
            Cell(" ", style(background="blue")),
            Cell("b", style(background="blue")),
            Cell("界", style(foreground="lime")),
            Cell("", style(foreground="lime")),
            Cell("c", style(background="navy")),
        ],
    )

    assert Frame(paint).svg() == (
        """<svg xmlns="http://www.w3.org/2000/svg" width="1.65em" height="2.26em">
 <style>svg {
  dominant-baseline: hanging;
  font-size: 1rem;
}
</style>
 <g shape-rendering="crispEdges">
  <rect x="0.00em" y="0.00em" width="1.65em" height="2.26em" fill="#000000" />
  <rect x="0.00em" y="0.00em" width="1.65em" height="1.13em" fill="#0000ff" />
  <rect x="0.00em" y="1.13em" width="1.10em" height="1.13em" fill="#000000" />
  <rect x="1.10em" y="1.13em" width="0.55em" height="1.13em" fill="#000080" />
 </g>
 <text fill="#ffffff" font-family="monospace">
  <tspan y="0.00em">
   <tspan x="0.00em" fill="#ff0000">a</tspan>
   <tspan x="1.10em">b</tspan>
  </tspan>
  <tspan y="1.13em">
   <tspan x="0.00em" fill="#00ff00">界</tspan>
   <tspan x="1.10em">c</tspan>
  </tspan>
 </text>
</svg>"""
    )


@pytest.mark.parametrize(
    ("cell_style", "expected"),
    [
        (CellStyle(), {}),
        (CellStyle(bold=True), {"font-weight": "bold"}),
        (CellStyle(dim=True), {"fill-opacity": "0.5"}),
        (CellStyle(italic=True), {"font-style": "italic"}),
        (CellStyle(underline=True), {"text-decoration": "underline"}),
        (CellStyle(strikethrough=True), {"text-decoration": "line-through"}),
        (CellStyle(underline=True, strikethrough=True), {"text-decoration": "underline line-through"}),
        (
            CellStyle(bold=True, italic=True, underline=True),
            {"font-weight": "bold", "font-style": "italic", "text-decoration": "underline"},
        ),
    ],
)
def test_svg_text_style_has_an_attribute_for_each_text_style_that_is_on(
    cell_style: CellStyle, expected: dict[str, str]
) -> None:
    assert svg_text_style(resolve_cell_style(cell_style)) == expected


def test_svg_draws_each_grapheme_with_its_text_style() -> None:
    paint = Paint(
        width=2,
        height=1,
        cells=[
            Cell("a", resolve_cell_style(CellStyle(foreground=Color.from_name("red"), bold=True))),
            Cell("b", resolve_cell_style(CellStyle(italic=True))),
        ],
    )

    text = svg(paint).find("text")
    assert text is not None
    assert [glyph.attrib for glyph in text.iter("tspan") if glyph.text] == [
        {"x": "0.00em", "fill": "#ff0000", "font-weight": "bold"},
        {"x": "0.55em", "font-style": "italic"},
    ]
