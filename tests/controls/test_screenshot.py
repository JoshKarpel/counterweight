from __future__ import annotations

import io
from pathlib import Path

import pytest

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import Quit
from counterweight.controls import Screenshot
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.hooks import use_state
from counterweight.output import Frame
from counterweight.output import paint_to_str
from counterweight.paint import Cell
from counterweight.paint import Paint
from counterweight.styles.styles import CellStyle
from counterweight.styles.styles import Color
from counterweight.styles.styles import as_solid
from counterweight.styles.styles import resolve_cell_style


@pytest.fixture
def frame() -> Frame:
    red = as_solid(resolve_cell_style(CellStyle(foreground=Color.from_name("red"))))
    return Frame(paint=Paint(2, 1, [Cell("h", red), Cell("i", red)]))


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
            children=(Text(content="a"),),
            on_input=lambda event, _: (Screenshot(handler=frames.append), Screenshot(handler=frames.append)),
        )

    await app(root(), headless=True, dimensions=(5, 2), autopilot=[KeyPressed(key="x"), Quit()], check_purity=True)

    assert len(frames) == 2
    assert frames[0] is frames[1]


async def test_frame_does_not_change_after_later_renders() -> None:
    frames: list[Frame] = []

    @component
    def root() -> Div:
        content, set_content = use_state("before")

        def on_input(event: InputEvent, _: Receiver) -> None:
            set_content("after")

        return Div(children=(Text(content=content),), on_input=on_input)

    await app(
        root(),
        headless=True,
        dimensions=(10, 1),
        autopilot=[Screenshot(handler=frames.append), KeyPressed(key="x"), Screenshot(handler=frames.append), Quit()],
        check_purity=True,
    )

    assert [frame.text(ansi=False).strip() for frame in frames] == ["before", "after"]


def test_to_file_creates_missing_parent_directories(tmp_path: Path, frame: Frame) -> None:
    path = tmp_path / "outer" / "inner" / "screenshot.txt"

    Screenshot.to_file(path).handler(frame)

    assert path.read_text() == frame.text(ansi=True)


def test_to_stream_prints_ansi_text_to_stderr_by_default(frame: Frame, capsys: pytest.CaptureFixture[str]) -> None:
    Screenshot.to_stream().handler(frame)

    assert capsys.readouterr() == ("", frame.text(ansi=True) + "\n")


def test_to_stream_flushes_after_printing(frame: Frame) -> None:
    flushed: list[str] = []

    class Stream(io.StringIO):
        def flush(self) -> None:
            flushed.append(self.getvalue())

    Screenshot.to_stream(Stream(), ansi=False).handler(frame)

    assert flushed == ["hi\n"]


def test_text_has_escape_codes_by_default() -> None:
    bold_red = as_solid(resolve_cell_style(CellStyle(foreground=Color.from_name("red"), bold=True)))
    plain = as_solid(resolve_cell_style(CellStyle()))
    frame = Frame(paint=Paint(2, 2, [Cell("a", bold_red), Cell("b", plain), Cell("c", plain), Cell("d", bold_red)]))

    red_bold = "\x1b[38;2;255;0;0m\x1b[48;2;0;0;0m\x1b[1m"
    white = "\x1b[38;2;255;255;255m\x1b[48;2;0;0;0m"
    assert frame.text() == f"{red_bold}a\x1b[0m{white}b\x1b[0m\n{white}c\x1b[0m{red_bold}d\x1b[0m"


def test_paint_to_str_has_escape_codes_by_default(frame: Frame) -> None:
    assert paint_to_str(frame.paint) == frame.text(ansi=True)
