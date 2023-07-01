import shutil
import sys
from collections.abc import Callable
from queue import Empty, Queue
from signal import SIG_DFL, SIGWINCH, signal
from threading import Thread
from time import perf_counter
from typing import List, TextIO, TypeVar

from structlog import get_logger

from reprisal.components.components import Component, build_concrete_element_tree, render_shadow_node_from_previous
from reprisal.events import AnyEvent, KeyPressed, TerminalResized
from reprisal.input import read_keys, start_input_control, stop_input_control
from reprisal.layout import BoxDimensions, Edge, Position, Rect, build_layout_tree, paint
from reprisal.logging import configure_logging
from reprisal.output import (
    apply_paint,
    start_mouse_reporting,
    start_output_control,
    stop_mouse_reporting,
    stop_output_control,
)
from reprisal.utils import diff

logger = get_logger()


def start_handling_resize_signal(queue: Queue[AnyEvent]) -> None:
    signal(SIGWINCH, lambda _, __: queue.put(TerminalResized()))


def stop_handling_resize_signal() -> None:
    signal(SIGWINCH, SIG_DFL)


def app(
    root: Callable[[], Component],
    output_stream: TextIO = sys.stdout,
    input_stream: TextIO = sys.stdin,
) -> None:
    configure_logging()

    logger.info("Application starting...")

    event_queue: Queue[AnyEvent] = Queue()

    original = start_input_control(stream=input_stream)
    try:
        start_handling_resize_signal(queue=event_queue)
        start_output_control(stream=output_stream)
        start_mouse_reporting(stream=output_stream)

        key_thread = Thread(target=read_keys, args=(event_queue, input_stream), daemon=True)
        key_thread.start()

        previous_full_paint: dict[Position, str] = {}

        needs_render = True
        shadow = render_shadow_node_from_previous(root(), None)
        while True:
            if needs_render:
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
                shadow = render_shadow_node_from_previous(root(), shadow)
                logger.debug("Rendered shadow tree", elapsed_ms=(perf_counter() - start_render) * 1000)

                start_render = perf_counter()
                element_tree = build_concrete_element_tree(shadow)
                logger.debug(
                    "Derived concrete element tree from shadow tree", elapsed_ms=(perf_counter() - start_render) * 1000
                )

                start_layout = perf_counter()
                layout_tree = build_layout_tree(element_tree)
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

                apply_paint(stream=output_stream, paint=diffed_paint)

                previous_full_paint = full_paint

                needs_render = False

            start_event_handling = perf_counter()
            events = drain_queue(event_queue)
            components = layout_tree.walk_from_bottom()
            for event in events:
                start_handle_event = perf_counter()
                match event:
                    case TerminalResized():
                        needs_render = True
                        previous_full_paint = {}
                    case KeyPressed():
                        for component in components:
                            if component.on_key:
                                needs_render = True
                                component.on_key(event)
                logger.debug("Handled event", event_=event, elapsed_ms=(perf_counter() - start_handle_event) * 1000)

            logger.debug(
                "Handled events", num_events=len(events), elapsed_ms=(perf_counter() - start_event_handling) * 1000
            )
    except KeyboardInterrupt as e:
        logger.debug(f"Caught {e!r}")
    finally:
        logger.info("Application stopping...")

        stop_mouse_reporting(stream=output_stream)
        stop_output_control(stream=output_stream)
        stop_input_control(stream=input_stream, original=original)
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
