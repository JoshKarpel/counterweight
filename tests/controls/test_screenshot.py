from __future__ import annotations

import io
from pathlib import Path

import pytest

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import Quit, Screenshot
from counterweight.elements import Div, Text
from counterweight.events import KeyPressed
from counterweight.geometry import Position
from counterweight.hooks import use_state
from counterweight.output import Frame
from counterweight.paint import P
from counterweight.styles.styles import CellStyle, Color, resolve_cell_style


@pytest.fixture
def frame() -> Frame:
    red = resolve_cell_style(CellStyle(foreground=Color.from_name("red")))
    return Frame(paint={Position(0, 0): P(char="h", style=red, z=0), Position(1, 0): P(char="i", style=red, z=0)})


@pytest.mark.parametrize("path_parts", [("screenshot.svg",), ("subdir", "screenshot.svg")])
def test_to_file_with_svg_suffix_writes_svg(tmp_path: Path, path_parts: tuple[str, ...], frame: Frame) -> None:
    path = tmp_path.joinpath(*path_parts)

    Screenshot.to_file(path).handler(frame)

    assert path.read_text() == frame.svg()


def test_to_file_with_txt_suffix_writes_ansi_text(tmp_path: Path, frame: Frame) -> None:
    path = tmp_path / "screenshot.txt"

    Screenshot.to_file(path).handler(frame)

    assert path.read_text() == frame.text(ansi=True)


def test_to_file_with_unknown_suffix_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"screenshot\.png"):
        Screenshot.to_file(tmp_path / "screenshot.png")


@pytest.mark.parametrize("ansi", [True, False])
def test_to_stream_prints_text(frame: Frame, ansi: bool) -> None:
    stream = io.StringIO()

    Screenshot.to_stream(stream, ansi=ansi).handler(frame)

    assert stream.getvalue() == frame.text(ansi=ansi) + "\n"


def test_plain_text_has_no_escape_codes(frame: Frame) -> None:
    assert frame.text(ansi=False) == "hi"


def test_ansi_text_has_escape_codes(frame: Frame) -> None:
    assert "\x1b[" in frame.text(ansi=True)


def test_svg_is_indented(frame: Frame) -> None:
    assert "\n <" in frame.svg()


async def test_screenshots_requested_in_one_cycle_receive_the_same_frame() -> None:
    frames: list[Frame] = []

    @component
    def root() -> Div:
        return Div(
            children=[
                Text(content="a", on_key=lambda _: Screenshot(handler=frames.append)),
                Text(content="b", on_key=lambda _: Screenshot(handler=frames.append)),
            ]
        )

    await app(root, headless=True, dimensions=(5, 2), autopilot=[KeyPressed(key="x"), Quit()])

    assert len(frames) == 2
    assert frames[0] is frames[1]


async def test_frame_does_not_change_after_later_renders() -> None:
    frames: list[Frame] = []

    @component
    def root() -> Div:
        content, set_content = use_state("before")

        def on_key(event: KeyPressed) -> None:
            set_content("after")

        return Div(children=[Text(content=content, on_key=on_key)])

    await app(
        root,
        headless=True,
        dimensions=(10, 1),
        autopilot=[Screenshot(handler=frames.append), KeyPressed(key="x"), Screenshot(handler=frames.append), Quit()],
    )

    assert [frame.text(ansi=False).strip() for frame in frames] == ["before", "after"]
