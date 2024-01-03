from counterweight.cell_paint import CellPaint


def test_cells_yields_self() -> None:
    assert tuple(CellPaint(char="f").cells) == (CellPaint(char="f"),)
