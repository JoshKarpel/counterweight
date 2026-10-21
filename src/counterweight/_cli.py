from __future__ import annotations

import os
import shlex
import subprocess
import sys
from asyncio import Queue
from asyncio import to_thread
from collections.abc import Mapping
from pathlib import Path
from typing import Never
from typing import TextIO

from more_itertools import one
from wcwidth import wcswidth
from without_cli import INT
from without_cli import PATH
from without_cli import STR
from without_cli import Streams
from without_cli import argument
from without_cli import command
from without_cli import flag
from without_cli import group
from without_cli import once
from without_cli import option
from without_cli import optional
from without_cli import run

from counterweight._app import app
from counterweight._constants import PACKAGE_NAME
from counterweight._constants import __version__
from counterweight._input import start_input_control
from counterweight._input import start_reading_keys
from counterweight._input import stop_input_control
from counterweight._input import stop_reading_keys
from counterweight._logging import last_devlog
from counterweight._logging import tail_devlog
from counterweight._output import Frame
from counterweight._output import start_bracketed_paste
from counterweight._output import start_mouse_tracking
from counterweight._output import stop_bracketed_paste
from counterweight._output import stop_mouse_tracking
from counterweight.components import component
from counterweight.controls import Quit
from counterweight.controls import Screenshot
from counterweight.elements import Text
from counterweight.events import AnyEvent
from counterweight.examples import gallery
from counterweight.examples.catalog import UnknownExample
from counterweight.examples.catalog import examples
from counterweight.examples.catalog import find
from counterweight.examples.catalog import shown
from counterweight.examples.catalog import write_copy
from counterweight.highlighting import code_block
from counterweight.styles.utilities import text_wrap_none

SIGINT_EXIT = 130
USAGE_EXIT = 2

# Kept in step by hand with the drawn logo, which codegen/generate_logo.py lays out on the same cells.
LOGO = "counter ╱\n       ╱ weight"


@command("version")
async def version(streams: Streams) -> int:
    """Display version information."""
    streams.stdout.write(f"{__version__}\n")
    return 0


@command(
    "devlog",
    option("--last", optional(INT), summary="Print the last N log messages and exit."),
    flag("--json", summary="Print the raw JSON lines instead of rendering them."),
)
async def devlog(streams: Streams, last: int | None, json: bool) -> int:
    """Tail the developer log file."""
    if last is not None:
        last_devlog(streams.stdout, last, raw=json)
    else:
        await tail_devlog(streams.stdout, raw=json)
    return 0


@command("check-input", flag("--mouse", summary="Also capture mouse inputs and show mouse events."))
async def check_input(streams: Streams, mouse: bool) -> int:
    """Show the events read from input (such as key presses), in the input-capture state an app runs in."""
    # Input capture and mouse tracking need the real terminal, which `streams` doesn't carry.
    return await _check_input(mouse=mouse, input_stream=sys.stdin, output_stream=sys.stdout)


async def _check_input(mouse: bool, input_stream: TextIO, output_stream: TextIO) -> Never:
    """
    Print every input read from `input_stream`, under the same input control as an app, until cancelled.
    Then stop reading input before handing the terminal back.
    """
    event_queue: Queue[AnyEvent] = Queue()

    original = start_input_control(stream=input_stream)
    key_reader = start_reading_keys(stream=input_stream, put_event=event_queue.put_nowait)
    try:
        start_bracketed_paste(stream=output_stream)
        if mouse:
            start_mouse_tracking(stream=output_stream)
        while True:
            output_stream.write("Waiting for input (press ctrl+c to exit)...\n")
            output_stream.flush()
            key = await event_queue.get()
            output_stream.write(f"{key!r}\n")
    finally:
        stop_reading_keys(key_reader)
        stop_input_control(stream=input_stream, original=original)
        stop_bracketed_paste(stream=output_stream)
        if mouse:
            stop_mouse_tracking(stream=output_stream)


@command("list", flag("--roots", summary="List each root of an example with several, by the name that runs it."))
async def list_examples(streams: Streams, roots: bool) -> int:
    """List the examples, apps first, by name and title."""
    catalog = examples()
    rows = [
        (example.root_name(root) if roots else example.name, example.title)
        for example in catalog
        for root in (example.roots if roots else example.roots[:1])
    ]
    width = max(len(name) for name, _ in rows)
    streams.stdout.write("".join(f"{name:<{width}}  {title}\n" for name, title in rows))
    return 0


@command("run", argument("name", once(STR), summary="The example, and a root after a colon for one of several."))
async def run_example(streams: Streams, name: str) -> int:
    """Run an example in the terminal."""
    try:
        _, root = find(name, examples())
    except UnknownExample as e:
        return unknown(streams, e)
    # The app needs the real terminal, which `streams` doesn't carry.
    await app(root())
    return 0


@command(
    "show",
    argument("name", once(STR), summary="The example."),
    option(("-o", "--output"), optional(PATH), summary="Write the source to this file instead."),
)
async def show(streams: Streams, name: str, output: Path | None) -> int:
    """Show an example's source, highlighted and paged in a terminal, and plain otherwise."""
    try:
        example, _ = find(name, examples())
    except UnknownExample as e:
        return unknown(streams, e)
    source = shown(await to_thread(example.source))
    if output is not None:
        await to_thread(output.write_text, source)
    elif sys.stdout.isatty():
        await to_thread(page, await painted(source), os.environ)
    else:
        streams.stdout.write(source)
    return 0


@command(
    "copy",
    argument("name", once(STR), summary="The example."),
    argument(
        "path", optional(PATH), summary="Where to write it, or a directory to write it in, the current one by default."
    ),
)
async def copy(streams: Streams, name: str, path: Path | None) -> int:
    """Copy an example to a file of your own, without what only the docs and the tests use, to start from."""
    if ":" in name:
        streams.stderr.write(f"copy copies a whole example, so name it without a root, as {name.partition(':')[0]}\n")
        return USAGE_EXIT
    try:
        example, _ = find(name, examples())
    except UnknownExample as e:
        return unknown(streams, e)
    try:
        destination = await to_thread(write_copy, example, path or Path.cwd())
    except FileExistsError as e:
        streams.stderr.write(f"{e.filename} already exists, so it's left as it is\n")
        return 1
    streams.stdout.write(f"Wrote {example.name} to {destination}\n")
    return 0


def unknown(streams: Streams, error: UnknownExample) -> int:
    """Says that a name names no example, and how to find the ones there are."""
    streams.stderr.write(f"{error}; `{PACKAGE_NAME} examples list` lists the examples\n")
    return USAGE_EXIT


async def painted(source: str) -> str:
    """`source` highlighted as Python, painted as a terminal would show it, in ANSI escape codes."""
    lines = source.splitlines()
    frames: list[Frame] = []
    await app(
        code_view(source),
        headless=True,
        dimensions=(max(max((wcswidth(line) for line in lines), default=0), 1), max(len(lines), 1)),
        autopilot=[Screenshot(handler=frames.append), Quit()],
    )
    return one(frames).text(ansi=True) + "\n"


@component
def code_view(source: str) -> Text:
    return code_block(source, "python", style=text_wrap_none)


def page(text: str, environ: Mapping[str, str]) -> None:
    """Shows `text` through the user's pager, `$PAGER`, or `less -R`, which keeps its colors."""
    pager = shlex.split(environ.get("PAGER", "")) or ["less", "-R"]
    subprocess.run(pager, input=text, text=True, check=False)


@command("gallery")
async def open_gallery(streams: Streams) -> int:
    """Browse the examples, and run each one in place."""
    # The gallery needs the real terminal, which `streams` doesn't carry.
    await app(gallery.root())
    return 0


examples_cli = group(
    "examples",
    commands=(open_gallery, list_examples, run_example, show, copy),
    summary="Run, read and copy the examples that ship with Counterweight.",
)


cli = group(
    PACKAGE_NAME,
    commands=(version, devlog, check_input, examples_cli),
    summary=f"{LOGO}\n\nCLI tools for Counterweight.",
    version=__version__,
)


def main() -> None:
    """The `counterweight` console script."""
    try:
        code = run(cli)
    except KeyboardInterrupt:
        code = SIGINT_EXIT
    raise SystemExit(code)
