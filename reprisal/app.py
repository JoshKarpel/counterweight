import shutil
import sys
from collections.abc import Callable
from functools import partial
from queue import Empty, Queue
from signal import SIG_DFL, SIGWINCH, signal
from threading import Thread
from time import perf_counter
from typing import List, TextIO, TypeVar

from structlog import get_logger

from reprisal.components import Div, Text
from reprisal.compositor import BoxDimensions, Edge, Position, Rect, build_layout_tree, paint
from reprisal.driver import (
    apply_paint,
    queue_keys,
    start_input_control,
    start_output_control,
    stop_input_control,
    stop_output_control,
)
from reprisal.events import AnyEvent, KeyPressed, TerminalResized
from reprisal.input import VTParser
from reprisal.logging import configure_logging
from reprisal.render import Root

logger = get_logger()


def start_handling_resize_signal(queue: Queue[AnyEvent]) -> None:
    signal(SIGWINCH, lambda _, __: queue.put(TerminalResized()))


def stop_handling_resize_signal() -> None:
    signal(SIGWINCH, SIG_DFL)


def app(
    func: Callable[[], Div | Text],
    output: TextIO = sys.stdout,
    input: TextIO = sys.stdin,
) -> None:
    configure_logging()

    logger.info("Application starting...")

    root = Root(func)

    event_queue: Queue[AnyEvent] = Queue()

    start_handling_resize_signal(queue=event_queue)
    original = start_input_control(stream=input)
    try:
        start_output_control(stream=output)

        key_thread = Thread(target=read_keys, args=(event_queue,), daemon=True)
        key_thread.start()

        previous_full_paint: dict[Position, str] = {}

        needs_render = True
        while True:
            if root.needs_render or needs_render:
                w, h = shutil.get_terminal_size()
                b = BoxDimensions(
                    # height is always zero here because this is the starting height of the context box in the layout algorithm
                    # screen boundary will need to be controlled by max height style and paint cutoff
                    content=Rect(x=0, y=0, width=w, height=0),
                    margin=Edge(),
                    border=Edge(),
                    padding=Edge(),
                )

                start_render = perf_counter()
                component_tree = root.render()
                logger.debug("Rendered component tree", elapsed_ms=(perf_counter() - start_render) * 1000)

                start_layout = perf_counter()
                layout_tree = build_layout_tree(component_tree)
                layout_tree.layout(b)
                logger.debug("Calculated layout", elapsed_ms=(perf_counter() - start_layout) * 1000)

                start_paint = perf_counter()
                full_paint = paint(layout_tree)
                logger.debug("Generated full paint", elapsed_ms=(perf_counter() - start_paint) * 1000)

                start_diff = perf_counter()
                diffed_paint = diff(full_paint, previous_full_paint)
                logger.debug(
                    "Diffed full paint from previous full paint", elapsed_ms=(perf_counter() - start_diff) * 1000
                )

                apply_paint(stream=output, paint=diffed_paint)

                previous_full_paint = full_paint

                needs_render = False

            for event in drain_queue(event_queue):
                match event:
                    case TerminalResized():
                        needs_render = True
                        previous_full_paint = {}
                    case KeyPressed():
                        for element in layout_tree.walk_from_bottom():
                            if element.on_key:
                                element.on_key(event)
    except KeyboardInterrupt as e:
        logger.debug(f"Caught {e!r}")
    finally:
        logger.info("Application stopping...")

        stop_output_control(stream=output)
        stop_input_control(stream=input, original=original)
        stop_handling_resize_signal()

        logger.info("Application stopped")


T = TypeVar("T")


def drain_queue(queue: Queue[T]) -> List[T]:
    items = [queue.get()]
    while True:
        try:
            items.append(queue.get(timeout=0.0001))
        except Empty:
            break

    return items


def read_keys(queue: Queue[AnyEvent]) -> None:
    parser = VTParser()
    handler = partial(queue_keys, queue=queue)

    while True:
        char = sys.stdin.read(1)
        logger.debug(f"read {char=} {ord(char)=} {hex(ord(char))=}")
        parser.advance(ord(char), handler=handler)


K = TypeVar("K")
V = TypeVar("V")


def diff(a: dict[K, V], b: dict[K, V]) -> dict[K, V]:
    d = {}
    for key in a.keys() | b.keys():
        a_val = a.get(key)
        if a_val != b.get(key) and a_val is not None:
            d[key] = a_val

    return d
