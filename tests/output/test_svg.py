from counterweight.output import Frame
from counterweight.paint import Cell, Paint
from counterweight.styles.styles import CellStyle, Color, ResolvedCellStyle, resolve_cell_style


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
