import os
from queue import Queue
from threading import Event, Thread

from counterweight.events import AnyEvent, KeyPressed
from counterweight.input import read_keys
from counterweight.keys import Key


def test_escape_at_the_end_of_input_is_the_escape_key_once_input_stops() -> None:
    read_fd, write_fd = os.pipe()
    events: Queue[AnyEvent] = Queue()
    allow, waiting = Event(), Event()
    allow.set()

    with os.fdopen(read_fd) as stream, os.fdopen(write_fd, "wb", buffering=0) as writer:
        Thread(target=read_keys, args=(stream, events.put, allow, waiting), daemon=True).start()

        writer.write(b"a\x1b")

        assert events.get(timeout=5) == KeyPressed(key="a")
        assert events.get(timeout=5) == KeyPressed(key=Key.Escape)

        allow.clear()
        waiting.wait()
