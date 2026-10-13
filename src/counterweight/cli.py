from __future__ import annotations

import sys
from asyncio import Queue, get_running_loop
from threading import Event, Thread

from without_cli import INT, Streams, command, flag, group, option, optional, run

from counterweight._context_vars import current_event_queue
from counterweight.constants import PACKAGE_NAME, __version__
from counterweight.events import AnyEvent
from counterweight.input import read_keys, start_input_control, stop_input_control
from counterweight.logging import last_devlog, tail_devlog
from counterweight.output import start_mouse_tracking, stop_mouse_tracking

SIGINT_EXIT = 130


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
    event_queue: Queue[AnyEvent] = Queue()
    current_event_queue.set(event_queue)

    loop = get_running_loop()

    def put_event(event: AnyEvent) -> None:
        loop.call_soon_threadsafe(event_queue.put_nowait, event)

    # Input capture needs the real terminal's file descriptors, which `streams` doesn't carry.
    input_stream = sys.stdin
    output_stream = sys.stdout

    allow, waiting = Event(), Event()
    allow.set()

    key_thread = Thread(
        target=read_keys,
        args=(
            input_stream,
            put_event,
            allow,
            waiting,
        ),
        daemon=True,
    )
    key_thread.start()

    original = start_input_control(stream=input_stream)
    if mouse:
        start_mouse_tracking(stream=output_stream)
    try:
        while True:
            streams.stdout.write("Waiting for input (press ctrl+c to exit)...\n")
            streams.stdout.flush()
            key = await event_queue.get()
            streams.stdout.write(f"{key!r}\n")
    finally:
        stop_input_control(stream=input_stream, original=original)
        if mouse:
            stop_mouse_tracking(stream=output_stream)


cli = group(
    PACKAGE_NAME,
    commands=(version, devlog, check_input),
    summary="CLI tools for Counterweight.",
    version=__version__,
)


def main() -> None:
    """The `counterweight` console script."""
    try:
        code = run(cli)
    except KeyboardInterrupt:
        code = SIGINT_EXIT
    raise SystemExit(code)


if __name__ == "__main__":
    main()
