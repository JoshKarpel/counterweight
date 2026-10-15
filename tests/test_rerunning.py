from __future__ import annotations

from asyncio import CancelledError
from asyncio import Event
from asyncio import Queue
from asyncio import TaskGroup
from asyncio import create_task
from asyncio import wait_for
from collections.abc import Callable
from contextlib import suppress
from copy import copy
from dataclasses import dataclass
from dataclasses import field
from datetime import timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from counterweight._utils import cancel_tasks
from counterweight._utils import forever
from counterweight.app import app
from counterweight.clock import BEGINNING
from counterweight.components import Component
from counterweight.components import component
from counterweight.controls import AnyControl
from counterweight.controls import Quit
from counterweight.controls import ToggleBorderHealing
from counterweight.elements import AnyElement
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import AnyEvent
from counterweight.events import InputEvent
from counterweight.events import Receiver
from counterweight.events import TerminalResized
from counterweight.focus import ElementHandle
from counterweight.geometry import Region
from counterweight.hooks import Rects
from counterweight.hooks import Setter
from counterweight.hooks import use_effect
from counterweight.hooks import use_rects
from counterweight.hooks import use_ref
from counterweight.hooks import use_state
from counterweight.hooks.hooks import rects_in
from counterweight.hooks.impls import Hooks
from counterweight.hooks.impls import InconsistentHookExecution
from counterweight.hooks.impls import NodeKey
from counterweight.hooks.impls import UseClock
from counterweight.hooks.impls import UseRef
from counterweight.layout import NO_LAYOUTS
from counterweight.layout import Layouts
from counterweight.shadow import ImpureComponent
from counterweight.shadow import ShadowNode
from counterweight.shadow import ShadowTree
from counterweight.shadow import dirty_paths
from counterweight.shadow import is_dirty
from counterweight.shadow import update_shadow
from tests.rendering import effect_tasks
from tests.rendering import render
from tests.rendering import state_set_keys
from tests.rendering import state_sets

type Shape = tuple[tuple[str, Shape], ...]


@dataclass(frozen=True, slots=True)
class Calls:
    """Which components ran, in order, and each one's setter, by name."""

    names: list[str] = field(default_factory=list)
    setters: dict[str, Setter[int]] = field(default_factory=dict)


@component
def counted(name: str, children: Shape, calls: Calls) -> Div:
    _, set_count = use_state(0)
    calls.names.append(name)
    calls.setters[name] = set_count
    return Div(children=tuple(counted(child, grandchildren, calls) for child, grandchildren in children))


def set_state(calls: Calls, queue: Queue[AnyEvent], *names: str) -> frozenset[NodeKey]:
    """Steps each named component's state, and returns the keys the render loop would collect from the queue."""
    for name in names:
        calls.setters[name](lambda count: count + 1)

    return state_set_keys(queue)


def rerun(
    root: Component | AnyElement,
    calls: Calls,
    *names: str,
    between: Callable[[], None] = lambda: None,
    check_purity: bool = False,
) -> tuple[ShadowNode, ShadowNode]:
    """
    Renders `root`, calls `between`, sets the named components' state, and renders the same `root` again.
    `check_purity` is off by default, since its extra calls would show up in `calls`.
    """
    with state_sets() as queue:
        previous = update_shadow(root, None, NO_LAYOUTS).tree
        between()
        dirty = set_state(calls, queue, *names)
        calls.names.clear()
        return previous.root, update_shadow(root, previous, NO_LAYOUTS, dirty, check_purity=check_purity).tree.root


def test_sibling_state_change_does_not_rerun_a_component() -> None:
    calls = Calls()

    rerun(counted("root", (("a", ()), ("b", ())), calls), calls, "b")

    assert calls.names == ["b"]


def test_parent_state_change_reruns_its_children() -> None:
    calls = Calls()

    rerun(counted("root", (("a", ()), ("b", ())), calls), calls, "root")

    assert calls.names == ["root", "a", "b"]


def test_grandchild_state_change_reruns_only_the_grandchild() -> None:
    calls = Calls()

    rerun(counted("root", (("middle", (("leaf", ()),)),), calls), calls, "leaf")

    assert calls.names == ["leaf"]


def test_ancestors_of_a_rerun_component_keep_their_elements() -> None:
    calls = Calls()

    previous, next = rerun(counted("root", (("middle", (("leaf", ()),)),), calls), calls, "leaf")

    assert (next.element is previous.element, next.children[0].element is previous.children[0].element) == (True, True)


def test_unchanged_frame_reuses_the_whole_tree() -> None:
    calls = Calls()

    previous, next = rerun(counted("root", (("a", ()),), calls), calls)

    assert next is previous


@component
def holds(child: Component, calls: Calls) -> Div:
    _, set_count = use_state(0)
    calls.names.append("holder")
    calls.setters["holder"] = set_count
    return Div(children=(child,))


def test_component_object_reused_by_its_rerun_parent_is_not_rerun() -> None:
    calls = Calls()

    rerun(holds(counted("held", (), calls), calls), calls, "holder")

    assert calls.names == ["holder"]


@component
def starts_every_render(log: list[str]) -> Text:
    async def setup() -> None:
        log.append("start")
        await forever()

    use_effect(setup)

    return Text(content="effect")


async def test_effect_without_deps_of_a_reused_component_does_not_rerun() -> None:
    log: list[str] = []
    calls = Calls()
    root = Div(children=(starts_every_render(log), counted("sibling", (), calls)))

    with state_sets() as queue:
        async with TaskGroup() as tg:
            shadow = await render(root, None, tg)
            shadow = await render(root, shadow, tg, set_state(calls, queue, "sibling"))
            log_after_sibling_rerun = log.copy()
            await cancel_tasks(effect_tasks(shadow))

    assert log_after_sibling_rerun == ["start"]


@component
def shows(log: list[str], setters: dict[str, Setter[bool]]) -> Div:
    is_shown, set_is_shown = use_state(True)
    setters["shows"] = set_is_shown

    @component
    def child() -> Text:
        async def setup() -> None:
            try:
                await forever()
            finally:
                log.append("stop")

        use_effect(setup, deps=())
        return Text(content="child")

    return Div(children=(child(),) if is_shown else ())


async def test_effect_stops_when_its_component_is_unmounted_by_a_rerun_parent() -> None:
    log: list[str] = []
    setters: dict[str, Setter[bool]] = {}
    root = shows(log, setters)

    with state_sets() as queue:
        async with TaskGroup() as tg:
            shadow = await render(root, None, tg)
            setters["shows"](False)
            await render(root, shadow, tg, state_set_keys(queue))

    assert log == ["stop"]


MOVED = Rects(
    content=Region(left=1, top=2, right=3, bottom=4),
    padding=Region(left=1, top=2, right=3, bottom=4),
    border=Region(left=1, top=2, right=3, bottom=4),
    margin=Region(left=1, top=2, right=3, bottom=4),
    clip=Region(left=0, top=0, right=10, bottom=10),
    visible=Region(left=1, top=2, right=3, bottom=4),
)


@component
def measures(calls: Calls) -> Div:
    use_rects()
    calls.names.append("measures")
    return Div()


@pytest.mark.parametrize(
    ("layout", "expected"),
    [
        pytest.param(MOVED, ["measures"], id="moved"),
        pytest.param(None, [], id="unmoved"),
    ],
)
def test_component_calling_use_rects_reruns_only_when_its_layout_moved(
    layout: Rects | None, expected: list[str]
) -> None:
    calls = Calls()
    root = measures(calls)
    previous = update_shadow(root, None, NO_LAYOUTS).tree
    layouts = Layouts(in_paint_order=(), by_key={} if layout is None else {previous.root.key: layout}, scrolls={})
    calls.names.clear()

    update_shadow(root, previous, layouts)

    assert calls.names == expected


NAMED = ElementHandle()


@component
def measures_named(calls: Calls) -> Div:
    use_rects(NAMED)
    calls.names.append("measures_named")
    return Div()


@pytest.mark.parametrize(
    ("moved", "expected"),
    [
        pytest.param("named", ["measures_named"], id="named-moved"),
        pytest.param("own", [], id="own-moved"),
    ],
)
def test_component_calling_use_rects_with_a_handle_reruns_only_when_the_element_it_names_moved(
    moved: str, expected: list[str]
) -> None:
    calls = Calls()
    root = Div(children=(measures_named(calls), Div(handle=NAMED)))
    previous = update_shadow(root, None, NO_LAYOUTS).tree
    reader, named = previous.root.children
    layouts = Layouts(
        in_paint_order=(),
        by_key={(named if moved == "named" else reader).key: MOVED},
        scrolls={},
        handles={NAMED: named.key},
    )
    calls.names.clear()

    update_shadow(root, previous, layouts)

    assert calls.names == expected


@component
def measures_until_set(calls: Calls) -> Div:
    is_measuring, set_is_measuring = use_state(True)
    calls.setters["measures_until_set"] = lambda _: set_is_measuring(False)
    if is_measuring:
        use_rects()
    calls.names.append("measures_until_set")
    return Div()


def test_component_that_stops_calling_use_rects_does_not_rerun_when_its_layout_moves() -> None:
    calls = Calls()
    root = measures_until_set(calls)
    with state_sets() as queue:
        first = update_shadow(root, None, NO_LAYOUTS).tree
        second = update_shadow(root, first, NO_LAYOUTS, set_state(calls, queue, "measures_until_set")).tree
    calls.names.clear()

    update_shadow(root, second, Layouts(in_paint_order=(), by_key={second.root.key: MOVED}, scrolls={}))

    assert calls.names == []


@pytest.mark.parametrize("memo", [False, True], ids=["plain", "memo"])
@pytest.mark.parametrize(
    ("autopilot", "expected_renders"),
    [
        pytest.param((TerminalResized(dimensions=(30, 12)),), 3, id="resize"),
        pytest.param((ToggleBorderHealing(),), 2, id="no-state-change"),
    ],
)
async def test_whole_tree_rerenders_only_on_resize(
    autopilot: tuple[AnyEvent | AnyControl, ...], expected_renders: int, memo: bool
) -> None:
    renders: list[str] = []

    @component(memo=memo)
    def leaf() -> Text:
        renders.append("leaf")
        return Text(content="leaf")

    @component
    def root() -> Div:
        return Div(children=(leaf(),))

    await app(root(), headless=True, dimensions=(20, 10), autopilot=(*autopilot, Quit()))

    # The warmup render and the first painted frame each render every component.
    assert len(renders) == expected_renders


@pytest.mark.parametrize("memo", [False, True], ids=["plain", "memo"])
async def test_effects_start_on_the_first_painted_frame(memo: bool) -> None:
    started = Event()

    @component(memo=memo)
    def starts() -> Div:
        async def setup() -> None:
            started.set()
            await forever()

        use_effect(setup, deps=())
        return Div()

    @component
    def root() -> Div:
        return Div(children=(starts(),))

    # Nothing yields to the event loop while an autopilot runs, so the app runs with none until the effect starts.
    running = create_task(app(root(), headless=True, dimensions=(20, 10)))
    try:
        await wait_for(started.wait(), timeout=5)
    finally:
        running.cancel()
        with suppress(CancelledError):
            await running

    assert started.is_set()


@st.composite
def dirty_trees(draw: st.DrawFn) -> tuple[ShadowNode, frozenset[NodeKey]]:
    """
    A tree of nodes, some with state set, some whose `use_rects` result has moved,
    and some whose `use_clock` is due at `NOW`, and the set keys.
    """
    shape = draw(st.recursive(st.just(()), lambda children: st.lists(children, max_size=3).map(tuple), max_leaves=12))

    def build(shape: tuple[object, ...]) -> ShadowNode:
        hooks = Hooks()
        read: list[dict[ElementHandle | None, Rects] | None] = [
            None,
            {None: rects_in(NO_LAYOUTS, hooks.key)},
            {None: MOVED},
        ]
        hooks.rects = draw(st.sampled_from(read))
        hooks.clocks = [copy(clock) for clock in draw(st.sampled_from([(), (DUE,), (NOT_DUE,), (NOT_DUE, DUE)]))]
        return ShadowNode(
            component=None,
            element=Text(content=""),
            hooks=hooks,
            children=tuple(build(child) for child in shape if isinstance(child, tuple)),
        )

    tree = build(shape)
    keys = [node.key for node in tree.walk()]
    dirty = draw(st.frozensets(st.sampled_from(keys)))
    return tree, dirty


NOW = BEGINNING + timedelta(seconds=90)
DUE = UseClock(interval=timedelta(minutes=1), mounted=BEGINNING, current=BEGINNING)
NOT_DUE = UseClock(interval=timedelta(minutes=1), mounted=BEGINNING, current=NOW)


@given(tree_and_dirty=dirty_trees())
def test_dirty_paths_are_the_nodes_with_a_dirty_node_in_their_subtree(
    tree_and_dirty: tuple[ShadowNode, frozenset[NodeKey]],
) -> None:
    tree, dirty = tree_and_dirty

    brute_force = frozenset(
        node.key for node in tree.walk() if any(is_dirty(below, dirty, NO_LAYOUTS, NOW) for below in node.walk())
    )

    _, paths = dirty_paths(ShadowTree(root=tree), dirty, NO_LAYOUTS, NOW)

    assert paths == brute_force


@given(tree_and_dirty=dirty_trees())
def test_dirty_paths_reports_each_dirty_node(tree_and_dirty: tuple[ShadowNode, frozenset[NodeKey]]) -> None:
    tree, dirty = tree_and_dirty

    dirty_nodes, _ = dirty_paths(ShadowTree(root=tree), dirty, NO_LAYOUTS, NOW)

    assert dirty_nodes == frozenset(node.key for node in tree.walk() if is_dirty(node, dirty, NO_LAYOUTS, NOW))


@given(tree_and_dirty=dirty_trees())
def test_shadow_tree_lists_its_nodes_in_pre_order(tree_and_dirty: tuple[ShadowNode, frozenset[NodeKey]]) -> None:
    tree, _ = tree_and_dirty

    assert ShadowTree(root=tree).nodes == tuple(tree.walk())


@component
def passes(calls: Calls, child: Callable[[int, Calls], Component]) -> Div:
    count, set_count = use_state(0)
    calls.names.append("parent")
    calls.setters["parent"] = set_count
    return Div(children=(child(count, calls),))


@component(memo=True)
def memo_leaf(argument: object, calls: Calls) -> Text:
    _, set_count = use_state(0)
    calls.names.append("leaf")
    calls.setters["leaf"] = set_count
    return Text(content=str(argument))


@pytest.mark.parametrize(
    ("child", "names", "expected"),
    [
        pytest.param(lambda count, calls: memo_leaf("same", calls), ("parent",), ["parent"], id="equal-arguments"),
        pytest.param(memo_leaf, ("parent",), ["parent", "leaf"], id="changed-arguments"),
        pytest.param(
            lambda count, calls: memo_leaf("same", calls),
            ("parent", "leaf"),
            ["parent", "leaf"],
            id="equal-arguments-and-own-state-changed",
        ),
        pytest.param(
            lambda count, calls: memo_leaf("same", calls).with_key(str(count)),
            ("parent",),
            ["parent", "leaf"],
            id="changed-key",
        ),
    ],
)
def test_memo_component_reruns_only_when_its_arguments_or_state_changed(
    child: Callable[[int, Calls], Component], names: tuple[str, ...], expected: list[str]
) -> None:
    calls = Calls()

    rerun(passes(calls, child), calls, *names)

    assert calls.names == expected


def test_component_without_memo_reruns_when_its_parent_does_with_equal_arguments() -> None:
    calls = Calls()

    rerun(passes(calls, lambda count, calls: counted("leaf", (), calls)), calls, "parent")

    assert calls.names == ["parent", "leaf"]


SETTINGS = {"label": "before"}


@component(memo=True)
def reads_setting(argument: object, calls: Calls) -> Text:
    calls.names.append("reads_setting")
    return Text(content=SETTINGS["label"])


@component(memo=True)
def handler_capturing_setting(argument: object, calls: Calls) -> Text:
    calls.names.append("handler_capturing_setting")
    label = SETTINGS["label"]

    def on_input(event: InputEvent, _: Receiver) -> None:
        print(label)  # pragma: never runs

    return Text(content="", on_input=on_input)


@component(memo=True)
def inline_handler(argument: object, calls: Calls) -> Text:
    calls.names.append("inline_handler")
    return Text(content="", on_input=lambda event, _: None)


@component
def reads_setting_around(child: Component, calls: Calls) -> Div:
    return Div(children=(child, Text(content=SETTINGS["label"])))


@pytest.mark.parametrize(
    ("root", "names", "stale"),
    [
        pytest.param(
            lambda calls: passes(calls, lambda count, calls: reads_setting("same", calls)),
            ("parent",),
            "reads_setting",
            id="memo-with-equal-arguments",
        ),
        pytest.param(
            lambda calls: passes(calls, lambda count, calls: handler_capturing_setting("same", calls)),
            ("parent",),
            "handler_capturing_setting",
            id="handler-captured-it",
        ),
        pytest.param(
            lambda calls: reads_setting_around(counted("leaf", (), calls), calls),
            ("leaf",),
            "reads_setting_around",
            id="passed-through-to-a-dirty-child",
        ),
        pytest.param(
            lambda calls: Div(children=(Div(children=(reads_setting("same", calls),)), counted("sibling", (), calls))),
            ("sibling",),
            "reads_setting",
            id="inside-a-reused-element",
        ),
    ],
)
def test_check_purity_raises_naming_a_reused_component_that_reads_a_changed_module_level_value(
    root: Callable[[Calls], Component | AnyElement],
    names: tuple[str, ...],
    stale: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = Calls()

    with pytest.raises(ImpureComponent, match=stale):
        rerun(
            root(calls),
            calls,
            *names,
            between=lambda: monkeypatch.setitem(SETTINGS, "label", "after"),
            check_purity=True,
        )


@pytest.mark.parametrize("child", [reads_setting, handler_capturing_setting, inline_handler], ids=lambda c: c.__name__)
def test_check_purity_runs_every_component_again_and_keeps_a_reused_one_whose_output_is_unchanged(
    child: Callable[[object, Calls], Component],
) -> None:
    calls = Calls()

    previous, next = rerun(passes(calls, lambda count, calls: child("same", calls)), calls, "parent", check_purity=True)

    assert (next.children[0] is previous.children[0], calls.names) == (True, ["parent", "parent", child.__name__])


@component(memo=True)
def has_effect(argument: object, calls: Calls) -> Text:
    calls.names.append("has_effect")

    async def setup() -> None:
        await forever()  # pragma: never runs

    use_effect(setup)
    return Text(content="")


def test_check_purity_leaves_a_reused_components_effect_hooks_unchanged() -> None:
    calls = Calls()
    root = passes(calls, lambda count, calls: has_effect("same", calls))

    with state_sets() as queue:
        previous = update_shadow(root, None, NO_LAYOUTS).tree
        before = [(effect.setup, effect.new_deps) for effect in previous.root.children[0].hooks.effects]
        dirty = set_state(calls, queue, "parent")
        calls.names.clear()
        next = update_shadow(root, previous, NO_LAYOUTS, dirty, check_purity=True).tree

    after = [(effect.setup, effect.new_deps) for effect in next.root.children[0].hooks.effects]
    assert (calls.names, after) == (["parent", "parent", "has_effect"], before)


@component
def counts_its_calls(calls: Calls) -> Text:
    calls.names.append("counts_its_calls")
    return Text(content=str(len(calls.names)))


def test_check_purity_raises_naming_a_component_that_ran_and_returns_something_different_when_run_again() -> None:
    calls = Calls()

    with pytest.raises(ImpureComponent, match="counts_its_calls"):
        rerun(passes(calls, lambda count, calls: counts_its_calls(calls)), calls, "parent", check_purity=True)


@component(memo=True)
def calls_state_once_setting_changes(argument: object, calls: Calls) -> Text:
    if SETTINGS["label"] == "after":
        use_state(0)
    return Text(content="")


def test_check_purity_raises_naming_a_reused_component_that_calls_a_different_number_of_hooks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = Calls()

    with pytest.raises(InconsistentHookExecution, match="calls_state_once_setting_changes"):
        rerun(
            passes(calls, lambda count, calls: calls_state_once_setting_changes("same", calls)),
            calls,
            "parent",
            between=lambda: monkeypatch.setitem(SETTINGS, "label", "after"),
            check_purity=True,
        )


@component(memo=True)
def counts_renders_in_a_ref(argument: object, calls: Calls) -> Text:
    renders = use_ref(0)
    renders.current += 1
    return Text(content="")


def test_check_purity_leaves_a_ref_that_a_reused_component_writes_while_rendering_unchanged() -> None:
    calls = Calls()

    _, next = rerun(
        passes(calls, lambda count, calls: counts_renders_in_a_ref("same", calls)), calls, "parent", check_purity=True
    )

    [hook] = next.children[0].hooks.data
    assert isinstance(hook, UseRef)
    assert hook.ref.current == 1


@component(memo=True)
def one_child_per_setting_letter(argument: object, calls: Calls) -> Div:
    return Div(children=tuple(Text(content=letter) for letter in SETTINGS["label"]))


def test_check_purity_leaves_every_node_mounted_when_running_again_unmounts_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = Calls()
    root = passes(calls, lambda count, calls: one_child_per_setting_letter("same", calls))

    with state_sets() as queue:
        previous = update_shadow(root, None, NO_LAYOUTS).tree
        monkeypatch.setitem(SETTINGS, "label", "after")
        dirty = set_state(calls, queue, "parent")
        with pytest.raises(ImpureComponent):
            update_shadow(root, previous, NO_LAYOUTS, dirty, check_purity=True)

    assert all(node.hooks.mount_status.is_mounted for node in previous.nodes)
