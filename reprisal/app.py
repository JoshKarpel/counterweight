import sys
from functools import partial
from queue import Empty, Queue
from typing import List, TypeVar

from reprisal.compositor import BoxDimensions, Edge, Rect, build_layout_tree, debug, paint
from reprisal.driver import no_echo, queue_keys
from reprisal.render import Root
from reprisal.vtparser import VTParser


def app(root):
    root = Root(root)

    parser = VTParser()

    key_queue = Queue()
    handler = partial(queue_keys, queue=key_queue)

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
        while True:
            char = sys.stdin.read(1)
            print(f"read {char=} {ord(char)=} {hex(ord(char))=}")
            parser.advance(ord(char), handler=handler)

            try:
                key_events = drain_queue(key_queue)
                for element in layout_tree.walk_from_bottom():
                    if element.on_key:
                        for key_event in key_events:
                            element.on_key(key_event)
            except Empty:
                print("key_queue empty")
                pass

            if root.needs_render:
                element_tree = root.render()
                layout_tree = build_layout_tree(element_tree)
                layout_tree.layout(b)
                p = paint(layout_tree)
                print(debug(p, layout_tree.dims.margin_rect()))


T = TypeVar("T")


def drain_queue(queue: Queue[T]) -> List[T]:
    items = []
    while True:
        try:
            items.append(queue.get_nowait())
        except Empty:
            break

    return items
