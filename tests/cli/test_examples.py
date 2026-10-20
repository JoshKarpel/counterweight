from __future__ import annotations

import re
import sys
from asyncio import Event
from asyncio import create_task
from asyncio import wait_for
from collections.abc import Sequence
from pathlib import Path

import pytest
from without_cli import Streams
from without_cli import run

from counterweight.cli import cli
from counterweight.examples.catalog import copied
from counterweight.examples.catalog import shown
from counterweight.examples.snippets import box_model
from counterweight.pseudoterminal import Exited
from counterweight.pseudoterminal import PtyConnection
from counterweight.pseudoterminal import run_pty
from tests.rendering import TIMEOUT

BOX_MODEL = Path(box_model.__file__)

ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def examples(*argv: str) -> tuple[int, str, str]:
    capture = Streams.captured()
    code = run(cli, argv=("examples", *argv), streams=capture.streams)
    return code, capture.stdout, capture.stderr


def test_list_shows_each_examples_name_and_title_with_the_apps_first() -> None:
    code, out, _ = examples("list")
    names = [line.split()[0] for line in out.splitlines()]

    assert (code, names[:2], "box-model" in names, out.splitlines()[0].split(maxsplit=1)[1]) == (
        0,
        ["chat", "markdown-viewer"],
        True,
        "Chat",
    )


def test_list_with_roots_names_each_root_of_an_example_with_several() -> None:
    _, out, _ = examples("list", "--roots")
    names = [line.split()[0] for line in out.splitlines()]

    assert ("layout-splitting:equal-grid" in names, "layout-splitting" in names, "box-model" in names) == (
        True,
        False,
        True,
    )


@pytest.mark.parametrize(
    "argv",
    [("run", "no-such-example"), ("show", "no-such-example"), ("copy", "no-such-example"), ("run", "box-model:nope")],
)
def test_naming_no_example_fails_and_says_how_to_list_them(argv: tuple[str, ...]) -> None:
    code, _, err = examples(*argv)

    assert (code, "counterweight examples list" in err) == (2, True)


def test_show_prints_the_plain_source_without_the_docs_markers_when_not_on_a_terminal() -> None:
    assert examples("show", "box-model") == (0, shown(BOX_MODEL.read_text()), "")


def test_show_writes_the_plain_source_to_a_file(tmp_path: Path) -> None:
    output = tmp_path / "box_model.py"

    code, _, _ = examples("show", "box-model", "-o", str(output))

    assert (code, output.read_text()) == (0, shown(BOX_MODEL.read_text()))


class Terminal:
    """Standard output as a terminal, which `show` pages to rather than printing on."""

    def isatty(self) -> bool:
        return True


def test_show_pages_the_highlighted_source_on_a_terminal(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    paged = tmp_path / "paged"
    monkeypatch.setattr(sys, "stdout", Terminal())
    monkeypatch.setenv("PAGER", f"sh -c 'cat > {paged}'")

    code, out, _ = examples("show", "box-model")

    text = paged.read_text()
    assert (code, out, "\x1b[" in text, "def root() -> Div:" in ANSI_ESCAPE.sub("", text)) == (0, "", True, True)


def test_copy_writes_the_example_as_it_runs_into_a_directory(tmp_path: Path) -> None:
    code, out, _ = examples("copy", "box-model", str(tmp_path))

    assert (code, (tmp_path / "box_model.py").read_text(), "box_model.py" in out) == (
        0,
        copied(BOX_MODEL.read_text()),
        True,
    )


def test_copy_writes_the_example_to_a_path_of_your_choosing(tmp_path: Path) -> None:
    code, _, _ = examples("copy", "box-model", str(tmp_path / "boxes.py"))

    assert (code, (tmp_path / "boxes.py").read_text()) == (0, copied(BOX_MODEL.read_text()))


def test_copy_leaves_a_file_that_is_already_there(tmp_path: Path) -> None:
    existing = tmp_path / "box_model.py"
    existing.write_text("mine")

    code, _, err = examples("copy", "box-model", str(tmp_path))

    assert (code, existing.read_text(), "already exists" in err) == (1, "mine", True)


def test_copy_takes_an_example_not_one_of_its_roots(tmp_path: Path) -> None:
    code, _, err = examples("copy", "layout-splitting:equal-grid", str(tmp_path))

    assert (code, "layout-splitting" in err, list(tmp_path.iterdir())) == (2, True, [])


async def run_until_ctrl_c(argv: Sequence[str], cwd: Path | None = None) -> Exited:
    """
    Runs `argv` on a pseudo-terminal, and once it has drawn something, presses Ctrl+C,
    which an app quits on, returning how the program exited.
    """
    drawn = Event()
    output = bytearray()
    started: list[PtyConnection] = []

    def read(data: bytes) -> None:
        output.extend(data)
        # Synchronized output wraps every frame, so its end means a whole frame has been drawn.
        if b"\x1b[?2026l" in output:
            drawn.set()

    running = create_task(run_pty(argv, 80, 24, on_output=read, on_start=started.append, cwd=cwd))
    await wait_for(drawn.wait(), TIMEOUT)
    started[0].write(b"\x03")
    outcome = await wait_for(running, TIMEOUT)
    assert isinstance(outcome, Exited)
    return outcome


async def test_run_runs_an_example_in_the_terminal_until_it_quits() -> None:
    outcome = await run_until_ctrl_c([sys.executable, "-m", "counterweight", "examples", "run", "box-model"])

    assert outcome == Exited(status=0)


@pytest.fixture
def copied_box_model(tmp_path: Path) -> Path:
    """The directory holding a copy of the box model snippet, as `counterweight examples copy` writes one."""
    (tmp_path / "box_model.py").write_text(copied(BOX_MODEL.read_text()))
    return tmp_path


async def test_a_copied_example_runs_on_its_own(copied_box_model: Path) -> None:
    outcome = await run_until_ctrl_c([sys.executable, "box_model.py"], cwd=copied_box_model)

    assert outcome == Exited(status=0)


async def test_gallery_opens_the_gallery_in_the_terminal_until_it_quits() -> None:
    outcome = await run_until_ctrl_c([sys.executable, "-m", "counterweight", "examples", "gallery"])

    assert outcome == Exited(status=0)
