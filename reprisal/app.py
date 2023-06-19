import shutil
import sys
from collections.abc import Callable
from functools import partial
from queue import Empty, Queue
from threading import Thread
from typing import List, TypeVar

from structlog import get_logger

from reprisal.components import Div, Text
from reprisal.compositor import BoxDimensions, Edge, Rect, build_layout_tree, paint
from reprisal.driver import Driver, queue_keys
from reprisal.input import VTParser
from reprisal.logging import configure_logging
from reprisal.render import Root
from reprisal.types import KeyQueueItem

logger = get_logger()


def app(func: Callable[[], Div | Text]) -> None:
    configure_logging()

    logger.info("Application starting...")

    root = Root(func)

    key_queue: Queue[KeyQueueItem] = Queue()
    w, h = shutil.get_terminal_size()
    b = BoxDimensions(
        # height is always zero here because this is the starting height of the context box in the layout algorithm
        # screen boundary will need to be controlled by max height style and paint cutoff
        content=Rect(x=0, y=0, width=w, height=0),
        margin=Edge(),
        border=Edge(),
        padding=Edge(),
    )

    driver = Driver()
    try:
        driver.start()

        key_thread = Thread(target=read_keys, args=(key_queue,), daemon=True)
        key_thread.start()

        while True:
            if root.needs_render:
                element_tree = root.render()
                layout_tree = build_layout_tree(element_tree)
                layout_tree.layout(b)
                p = paint(layout_tree)
                driver.apply_paint(p, (w, h))
                # driver.apply_paint({Position(0, 0): "*"})
                # print(debug(p, layout_tree.dims.margin_rect()))

            key_events = drain_queue(key_queue)
            for element in layout_tree.walk_from_bottom():
                if element.on_key:
                    for key_event in key_events:
                        element.on_key(key_event)
    finally:
        driver.stop()


T = TypeVar("T")


def drain_queue(queue: Queue[T]) -> List[T]:
    items = [queue.get()]
    while True:
        try:
            items.append(queue.get(timeout=0.0001))
        except Empty:
            break

    return items


def read_keys(key_queue: Queue[KeyQueueItem]) -> None:
    parser = VTParser()
    handler = partial(queue_keys, queue=key_queue)

    while True:
        char = sys.stdin.read(1)
        logger.debug(f"read {char=} {ord(char)=} {hex(ord(char))=}")
        parser.advance(ord(char), handler=handler)
