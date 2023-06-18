import sys
from functools import partial
from queue import Empty, Queue
from threading import Thread
from typing import List, TypeVar

from structlog import get_logger

from reprisal.compositor import BoxDimensions, Edge, Rect, build_layout_tree, debug, paint
from reprisal.driver import no_echo, queue_keys
from reprisal.input import VTParser
from reprisal.render import Root

logger = get_logger()


def app(root):
    root = Root(root)

    key_queue = Queue()
    b = BoxDimensions(
        content=Rect(x=0, y=0, width=60, height=0),
        margin=Edge(),
        border=Edge(),
        padding=Edge(),
    )

    element_tree = root.render()
    layout_tree = build_layout_tree(element_tree)
    layout_tree.layout(b)
    p = paint(layout_tree)
    print(debug(p, layout_tree.dims.margin_rect()))

    with no_echo():
        key_thread = Thread(target=read_keys, args=(key_queue,), daemon=True)
        key_thread.start()

        while True:
            key_events = drain_queue(key_queue)
            for element in layout_tree.walk_from_bottom():
                if element.on_key:
                    for key_event in key_events:
                        element.on_key(key_event)

            if root.needs_render:
                element_tree = root.render()
                layout_tree = build_layout_tree(element_tree)
                layout_tree.layout(b)
                p = paint(layout_tree)
                print(debug(p, layout_tree.dims.margin_rect()))


T = TypeVar("T")


def drain_queue(queue: Queue[T]) -> List[T]:
    items = [queue.get()]
    while True:
        try:
            items.append(queue.get(timeout=0.0001))
        except Empty:
            break

    return items


def read_keys(key_queue: Queue) -> None:
    parser = VTParser()
    handler = partial(queue_keys, queue=key_queue)

    while True:
        char = sys.stdin.read(1)
        logger.debug(f"read {char=} {ord(char)=} {hex(ord(char))=}")
        parser.advance(ord(char), handler=handler)
