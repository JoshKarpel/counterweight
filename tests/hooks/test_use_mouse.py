from asyncio import TaskGroup
from collections.abc import Callable
from dataclasses import replace
from weakref import WeakSet

import pytest

from counterweight._context_vars import current_use_mouse_listeners
from counterweight._utils import cancel_tasks
from counterweight.components import component
from counterweight.elements import Text
from counterweight.geometry import Position
from counterweight.geometry import Rects
from counterweight.geometry import Region
from counterweight.hooks import Hovered
from counterweight.hooks import Mouse
from counterweight.hooks import use_hovered
from counterweight.hooks import use_mouse
from counterweight.layout import NO_LAYOUTS
from counterweight.layout import Layouts
from counterweight.shadow import update_shadow
from tests.rendering import effect_tasks
from tests.rendering import render
from tests.rendering import state_sets

# Each box is a cell inside the next.
NESTED_BOXES = Rects(
    content=Region(left=3, top=3, right=8, bottom=6),
    padding=Region(left=2, top=2, right=9, bottom=7),
    border=Region(left=1, top=1, right=10, bottom=8),
    margin=Region(left=0, top=0, right=11, bottom=9),
    clip=Region(left=0, top=0, right=20, bottom=10),
    visible=Region(left=1, top=1, right=10, bottom=8),
)
CLIPPED_AT_COLUMN_3 = replace(
    NESTED_BOXES, clip=Region(left=0, top=0, right=3, bottom=10), visible=Region(left=1, top=1, right=3, bottom=8)
)
CLIPPED_AWAY = replace(NESTED_BOXES, clip=None, visible=None)


@component
def records_mouse(label: str, recorded: list[Mouse]) -> Text:
    recorded.append(use_mouse())
    return Text(content=label)


def test_use_mouse_reads_off_screen_and_still_before_the_mouse_moves() -> None:
    recorded: list[Mouse] = []
    token = current_use_mouse_listeners.set(WeakSet[Callable[[Mouse], None]]())

    try:
        with state_sets():
            update_shadow(records_mouse("first", recorded), None, NO_LAYOUTS)
    finally:
        current_use_mouse_listeners.reset(token)

    assert recorded == [Mouse(absolute=Position(-1, -1), motion=Position(0, 0), button=None)]


async def test_use_mouse_keeps_its_subscription_when_the_component_reruns() -> None:
    recorded: list[Mouse] = []
    token = current_use_mouse_listeners.set(WeakSet[Callable[[Mouse], None]]())

    try:
        with state_sets():
            async with TaskGroup() as tg:
                shadow = await render(records_mouse("first", recorded), None, tg)
                tasks_after_mount = effect_tasks(shadow)
                shadow = await render(records_mouse("second", recorded), shadow, tg)
                tasks_after_rerun = effect_tasks(shadow)
                await cancel_tasks(tasks_after_rerun)
    finally:
        current_use_mouse_listeners.reset(token)

    assert (len(recorded), tasks_after_rerun) == (2, tasks_after_mount)


NOWHERE = Hovered(content=False, padding=False, border=False, margin=False)


@pytest.mark.parametrize(
    ("rects", "position", "expected"),
    [
        pytest.param(
            NESTED_BOXES,
            Position(4, 4),
            Hovered(content=True, padding=True, border=True, margin=True),
            id="in-the-content",
        ),
        pytest.param(
            NESTED_BOXES,
            Position(2, 4),
            Hovered(content=False, padding=True, border=True, margin=True),
            id="in-the-padding",
        ),
        pytest.param(
            NESTED_BOXES,
            Position(1, 4),
            Hovered(content=False, padding=False, border=True, margin=True),
            id="on-the-border",
        ),
        pytest.param(
            NESTED_BOXES,
            Position(0, 4),
            Hovered(content=False, padding=False, border=False, margin=True),
            id="in-the-margin",
        ),
        pytest.param(NESTED_BOXES, Position(15, 4), NOWHERE, id="outside"),
        pytest.param(
            CLIPPED_AT_COLUMN_3,
            Position(2, 4),
            Hovered(content=False, padding=True, border=True, margin=True),
            id="in-the-padding-inside-the-clip",
        ),
        pytest.param(CLIPPED_AT_COLUMN_3, Position(4, 4), NOWHERE, id="in-the-content-outside-the-clip"),
        pytest.param(CLIPPED_AWAY, Position(4, 4), NOWHERE, id="in-the-content-of-an-element-clipped-away"),
    ],
)
async def test_use_hovered_reports_which_of_its_boxes_the_mouse_is_in_inside_its_clip(
    rects: Rects, position: Position, expected: Hovered
) -> None:
    recorded: list[Hovered] = []
    listeners = WeakSet[Callable[[Mouse], None]]()
    token = current_use_mouse_listeners.set(listeners)

    @component
    def hovers() -> Text:
        recorded.append(use_hovered())
        return Text(content="hover")

    try:
        with state_sets():
            async with TaskGroup() as tg:
                shadow = await render(hovers(), None, tg)
                for listener in list(listeners):
                    listener(Mouse(absolute=position, motion=Position(0, 0), button=None))
                layouts = Layouts(in_paint_order=(), by_key={shadow.root.key: rects}, scrolls={})
                shadow = update_shadow(hovers(), shadow, layouts).tree
                await cancel_tasks(effect_tasks(shadow))
    finally:
        current_use_mouse_listeners.reset(token)

    assert recorded[-1] == expected
