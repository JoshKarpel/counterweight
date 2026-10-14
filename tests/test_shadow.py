from __future__ import annotations

import gc
from asyncio import TaskGroup
from collections.abc import Callable
from datetime import timedelta
from sys import getrecursionlimit
from weakref import WeakSet, ref

import pytest

from counterweight._context_vars import (
    current_hook_idx,
    current_hook_state,
    current_use_mouse_listeners,
)
from counterweight._utils import cancel_tasks, forever
from counterweight.components import component
from counterweight.elements import Div, Text
from counterweight.hooks import (
    ElementHandle,
    Mouse,
    Setter,
    use_clock,
    use_effect,
    use_focus,
    use_memo,
    use_mouse,
    use_ref,
    use_state,
)
from counterweight.hooks.impls import Hooks, InconsistentHookExecution
from counterweight.layout import NO_LAYOUTS
from counterweight.shadow import (
    DuplicateElementHandle,
    DuplicateKey,
    ShadowNode,
    ShadowTree,
    ShadowUpdate,
    update_shadow,
)
from tests.rendering import effect_tasks, render, state_sets


@component
def logs_effect(name: str, log: list[str]) -> Text:
    async def setup() -> None:
        log.append(f"start {name}")
        try:
            await forever()
        finally:
            log.append(f"stop {name}")

    use_effect(setup=setup, deps=())

    return Text(content=name)


@component
def logs_effect_per_dep(name: str, dep: int, log: list[str]) -> Text:
    async def setup() -> None:
        log.append(f"start {name} {dep}")
        try:
            await forever()
        finally:
            log.append(f"stop {name} {dep}")

    use_effect(setup=setup, deps=(dep,))

    return Text(content=name)


async def test_rerun_effect_stops_before_it_starts_again() -> None:
    log: list[str] = []

    async with TaskGroup() as tg:
        shadow = await render(logs_effect_per_dep("A", 1, log), None, tg)
        shadow = await render(logs_effect_per_dep("A", 2, log), shadow, tg)
        log_after_rerun = log.copy()
        await cancel_tasks(effect_tasks(shadow))

    assert log_after_rerun == ["start A 1", "stop A 1", "start A 2"]


async def test_unmounted_effect_stops_before_sibling_rerun_starts() -> None:
    log: list[str] = []

    async with TaskGroup() as tg:
        shadow = await render(Div(children=(logs_effect_per_dep("A", 1, log), logs_effect("B", log))), None, tg)
        shadow = await render(Div(children=(logs_effect_per_dep("A", 2, log),)), shadow, tg)
        log_after_rerender = log.copy()
        await cancel_tasks(effect_tasks(shadow))

    assert log_after_rerender.index("stop B") < log_after_rerender.index("start A 2")


async def test_component_replaced_by_element_stops_its_effect() -> None:
    log: list[str] = []

    async with TaskGroup() as tg:
        shadow = await render(Div(children=(logs_effect("A", log),)), None, tg)
        shadow = await render(Div(children=(Div(),)), shadow, tg)
        log_after_replacement = log.copy()
        await cancel_tasks(effect_tasks(shadow))

    assert log_after_replacement == ["start A", "stop A"]


async def test_component_nested_under_replaced_component_starts_with_initial_state() -> None:
    setters: list[Setter[int]] = []
    seen: list[int] = []

    @component
    def counter() -> Text:
        count, set_count = use_state(3)
        setters.append(set_count)
        seen.append(count)
        return Text(content=str(count))

    @component
    def wrapper() -> Div:
        return Div(children=(counter(),))

    with state_sets():
        async with TaskGroup() as tg:
            shadow = await render(Div(children=(wrapper(),)), None, tg)
            setters[-1](7)
            await render(Div(children=(Div(children=(counter(),)),)), shadow, tg)

    assert seen == [3, 3]


async def test_use_mouse_listener_removed_when_component_replaced_by_element() -> None:
    listeners: WeakSet[Callable[[Mouse], None]] = WeakSet()
    token = current_use_mouse_listeners.set(listeners)

    @component
    def tracks_mouse() -> Text:
        use_mouse()
        return Text(content="mouse")

    try:
        async with TaskGroup() as tg:
            shadow = await render(Div(children=(tracks_mouse(),)), None, tg)
            listener_count_while_mounted = len(listeners)
            shadow = await render(Div(children=(Div(),)), shadow, tg)
            listener_count_after_replacement = len(listeners)
            await cancel_tasks(effect_tasks(shadow))
    finally:
        current_use_mouse_listeners.reset(token)

    assert (listener_count_while_mounted, listener_count_after_replacement) == (1, 0)


def leaf(name: str, *children: ShadowNode) -> ShadowNode:
    return ShadowNode(component=None, element=Text(content=name), hooks=Hooks(), children=children)


def test_walk_yields_nodes_in_pre_order() -> None:
    tree = leaf("root", leaf("a", leaf("a1"), leaf("a2")), leaf("b", leaf("b1")))

    names = [node.element.content for node in tree.walk() if isinstance(node.element, Text)]

    assert names == ["root", "a", "a1", "a2", "b", "b1"]


def test_walk_handles_trees_deeper_than_the_recursion_limit() -> None:
    depth = getrecursionlimit() * 2
    tree = leaf("bottom")
    for _ in range(depth):
        tree = leaf("link", tree)

    assert sum(1 for _ in tree.walk()) == depth + 1


def shadow_update(ran: list[Hooks], unmounted: list[Hooks], mounted: list[Hooks]) -> ShadowUpdate:
    return ShadowUpdate(
        tree=ShadowTree(root=leaf("root")),
        ran=tuple(ran),
        unmounted=tuple(unmounted),
        mounted=frozenset(hooks.key for hooks in mounted),
    )


def test_a_node_that_ran_in_both_updates_ran_once_in_the_combined_update() -> None:
    first, both, later = Hooks(), Hooks(), Hooks()

    combined = shadow_update([first, both], [], []).followed_by(shadow_update([both, later], [], []))

    assert [hooks.key for hooks in combined.ran] == [first.key, both.key, later.key]


def test_a_node_mounted_by_the_first_update_and_unmounted_by_the_later_neither_ran_nor_mounted() -> None:
    kept, dropped = Hooks(), Hooks()

    combined = shadow_update([kept, dropped], [], [kept, dropped]).followed_by(shadow_update([], [dropped], []))

    assert ([hooks.key for hooks in combined.ran], combined.mounted, [hooks.key for hooks in combined.unmounted]) == (
        [kept.key],
        {kept.key},
        [dropped.key],
    )


def test_the_combined_update_has_the_later_updates_tree() -> None:
    later = shadow_update([], [], [])

    combined = shadow_update([], [], []).followed_by(later)

    assert combined.tree is later.tree


@component
def remembers(name: str, setters: dict[str, Setter[str]], seen: dict[str, str]) -> Text:
    value, set_value = use_state("initial")
    setters[name] = set_value
    seen[name] = value
    return Text(content=value)


async def test_reordered_keyed_children_keep_their_state() -> None:
    setters: dict[str, Setter[str]] = {}
    seen: dict[str, str] = {}

    with state_sets():
        async with TaskGroup() as tg:
            shadow = await render(
                Div(children=tuple(remembers(name, setters, seen).with_key(name) for name in ("x", "y"))), None, tg
            )
            setters["x"]("x was set")
            setters["y"]("y was set")
            await render(
                Div(children=tuple(remembers(name, setters, seen).with_key(name) for name in ("y", "x"))), shadow, tg
            )

    assert seen == {"x": "x was set", "y": "y was set"}


async def test_reordered_keyed_children_keep_their_effects_running() -> None:
    log: list[str] = []

    async with TaskGroup() as tg:
        shadow = await render(
            Div(children=tuple(logs_effect(name, log).with_key(name) for name in ("x", "y"))), None, tg
        )
        shadow = await render(
            Div(children=tuple(logs_effect(name, log).with_key(name) for name in ("y", "x"))), shadow, tg
        )
        log_after_reorder = log.copy()
        await cancel_tasks(effect_tasks(shadow))

    assert log_after_reorder == ["start x", "start y"]


async def test_keyed_children_after_a_removed_keyed_child_keep_their_state() -> None:
    setters: dict[str, Setter[str]] = {}
    seen: dict[str, str] = {}

    with state_sets():
        async with TaskGroup() as tg:
            shadow = await render(
                Div(children=tuple(remembers(name, setters, seen).with_key(name) for name in ("a", "b", "c"))),
                None,
                tg,
            )
            setters["c"]("c was set")
            await render(
                Div(children=tuple(remembers(name, setters, seen).with_key(name) for name in ("a", "c"))), shadow, tg
            )

    assert seen["c"] == "c was set"


async def test_inserting_a_keyed_child_at_the_front_mounts_only_that_child() -> None:
    log: list[str] = []

    async with TaskGroup() as tg:
        shadow = await render(
            Div(children=tuple(logs_effect(name, log).with_key(name) for name in ("x", "y"))), None, tg
        )
        shadow = await render(
            Div(children=tuple(logs_effect(name, log).with_key(name) for name in ("w", "x", "y"))), shadow, tg
        )
        log_after_insert = log.copy()
        await cancel_tasks(effect_tasks(shadow))

    assert log_after_insert == ["start x", "start y", "start w"]


async def test_unkeyed_child_after_a_removed_keyed_sibling_remounts() -> None:
    log: list[str] = []

    async with TaskGroup() as tg:
        shadow = await render(Div(children=(logs_effect("a", log).with_key("a"), logs_effect("u", log))), None, tg)
        shadow = await render(Div(children=(logs_effect("u", log),)), shadow, tg)
        log_after_removal = log.copy()
        await cancel_tasks(effect_tasks(shadow))

    assert log_after_removal.count("start u") == 2


def test_duplicate_sibling_keys_raise() -> None:
    log: list[str] = []

    with pytest.raises(DuplicateKey, match=r"^Sibling components share the key 'k'$"):
        update_shadow(
            Div(children=(logs_effect("x", log).with_key("k"), logs_effect("y", log).with_key("k"))), None, NO_LAYOUTS
        )


def test_two_mounted_elements_given_one_handle_raise_naming_the_handle() -> None:
    handle = ElementHandle()

    with pytest.raises(DuplicateElementHandle) as raised:
        update_shadow(Div(children=(Div(handle=handle), Text(content="", handle=handle))), None, NO_LAYOUTS)

    assert repr(handle) in str(raised.value)


async def test_setter_is_the_same_object_across_renders() -> None:
    setters: dict[str, Setter[str]] = {}
    seen: dict[str, str] = {}
    setters_by_render: list[Setter[str]] = []

    with state_sets():
        async with TaskGroup() as tg:
            shadow = await render(remembers("a", setters, seen), None, tg)
            setters_by_render.append(setters["a"])
            setters["a"]("a was set")
            await render(remembers("a", setters, seen), shadow, tg)
            setters_by_render.append(setters["a"])

    assert setters_by_render[0] is setters_by_render[1]


async def test_effect_with_setter_in_deps_runs_once_across_renders() -> None:
    log: list[str] = []

    @component
    def depends_on_setter(label: str) -> Text:
        _, set_value = use_state(0)

        async def setup() -> None:
            log.append("start")
            await forever()

        use_effect(setup=setup, deps=(set_value,))

        return Text(content=label)

    async with TaskGroup() as tg:
        shadow = await render(depends_on_setter("first"), None, tg)
        shadow = await render(depends_on_setter("second"), shadow, tg)
        shadow = await render(depends_on_setter("third"), shadow, tg)
        log_after_renders = log.copy()
        await cancel_tasks(effect_tasks(shadow))

    assert log_after_renders == ["start"]


@component
def wraps_remembers(setters: dict[str, Setter[str]], seen: dict[str, str]) -> Div:
    return Div(children=(remembers("nested", setters, seen),))


@pytest.mark.parametrize(
    ("before", "after", "name"),
    [
        pytest.param(
            lambda s, v: Div(children=(remembers("a", s, v),)),
            lambda s, v: Div(children=(Div(),)),
            "a",
            id="replaced-by-element",
        ),
        pytest.param(
            lambda s, v: Div(children=(remembers("a", s, v).with_key("a"), remembers("b", s, v).with_key("b"))),
            lambda s, v: Div(children=(remembers("b", s, v).with_key("b"),)),
            "a",
            id="removed-keyed-sibling",
        ),
        pytest.param(
            lambda s, v: Div(children=(remembers("a", s, v), remembers("b", s, v))),
            lambda s, v: Div(children=(remembers("a", s, v),)),
            "b",
            id="removed-trailing-unkeyed-child",
        ),
        pytest.param(
            lambda s, v: Div(children=(remembers("a", s, v),)),
            lambda s, v: Div(children=(wraps_remembers(s, v),)),
            "a",
            id="replaced-by-other-component",
        ),
        pytest.param(
            lambda s, v: Div(children=(wraps_remembers(s, v),)),
            lambda s, v: Div(children=(Div(),)),
            "nested",
            id="nested-under-replaced-component",
        ),
    ],
)
async def test_setter_called_after_unmount_enqueues_nothing(
    before: Callable[[dict[str, Setter[str]], dict[str, str]], Div],
    after: Callable[[dict[str, Setter[str]], dict[str, str]], Div],
    name: str,
) -> None:
    setters: dict[str, Setter[str]] = {}
    seen: dict[str, str] = {}

    with state_sets() as queue:
        async with TaskGroup() as tg:
            shadow = await render(before(setters, seen), None, tg)
            await render(after(setters, seen), shadow, tg)
            setters[name]("set after unmount")

    assert queue.empty()


def test_unmounted_state_is_freed_without_the_cycle_collector() -> None:
    setters: dict[str, Setter[str]] = {}
    seen: dict[str, str] = {}
    shadow = update_shadow(Div(children=(remembers("a", setters, seen),)), None, NO_LAYOUTS).tree
    state = ref(shadow.root.children[0].hooks.data[0])

    gc.disable()
    try:
        shadow = update_shadow(Div(children=(Div(),)), shadow, NO_LAYOUTS).tree
        is_freed = state() is None
    finally:
        gc.enable()

    assert is_freed


async def test_setter_of_moved_keyed_child_still_enqueues() -> None:
    setters: dict[str, Setter[str]] = {}
    seen: dict[str, str] = {}

    with state_sets() as queue:
        async with TaskGroup() as tg:
            shadow = await render(
                Div(children=tuple(remembers(name, setters, seen).with_key(name) for name in ("x", "y"))), None, tg
            )
            await render(
                Div(children=tuple(remembers(name, setters, seen).with_key(name) for name in ("y", "x"))), shadow, tg
            )
            setters["x"]("set after move")

    assert queue.qsize() == 1


@component
def calls_hooks(hook_count: int) -> Text:
    for _ in range(hook_count):
        use_state(0)
    return Text(content=str(hook_count))


@pytest.mark.parametrize(
    ("first_count", "second_count"),
    [
        pytest.param(2, 1, id="skips-last-hook"),
        pytest.param(1, 2, id="adds-a-hook"),
    ],
)
def test_changing_hook_count_between_renders_raises(first_count: int, second_count: int) -> None:
    shadow = update_shadow(calls_hooks(first_count), None, NO_LAYOUTS).tree

    with pytest.raises(InconsistentHookExecution):
        update_shadow(calls_hooks(second_count), shadow, NO_LAYOUTS).tree


async def never_runs() -> None:
    raise AssertionError("update_shadow doesn't start effects")


HOOK_CALLS: dict[str, Callable[[], object]] = {
    "UseState": lambda: use_state(0),
    "UseRef": lambda: use_ref(0),
    "UseEffect": lambda: use_effect(never_runs, deps=()),
    "UseMemo": lambda: use_memo(lambda: 0, deps=()),
    "UseClock": lambda: use_clock(timedelta(seconds=1)),
    "UseFocus": use_focus,
}


@component
def calls_hook(name: str) -> Text:
    HOOK_CALLS[name]()
    return Text(content=name)


@pytest.mark.parametrize(
    ("first", "second"),
    [
        pytest.param("UseRef", "UseState", id="use_state"),
        pytest.param("UseEffect", "UseRef", id="use_ref"),
        pytest.param("UseMemo", "UseEffect", id="use_effect"),
        pytest.param("UseClock", "UseMemo", id="use_memo"),
        pytest.param("UseFocus", "UseClock", id="use_clock"),
        pytest.param("UseState", "UseFocus", id="use_focus"),
    ],
)
def test_calling_a_different_hook_in_the_same_place_raises_naming_both(first: str, second: str) -> None:
    shadow = update_shadow(calls_hook(first), None, NO_LAYOUTS).tree

    with pytest.raises(
        InconsistentHookExecution, match=rf"^Expected a {second} hook, but got a {first} hook instead\.$"
    ):
        update_shadow(calls_hook(second), shadow, NO_LAYOUTS)


def test_a_components_keyword_arguments_reach_its_function() -> None:
    @component
    def labeled(*, label: str) -> Text:
        return Text(content=label)

    shadow = update_shadow(labeled(label="from a keyword"), None, NO_LAYOUTS).tree

    assert shadow.root.element == Text(content="from a keyword")


def test_calling_the_same_hooks_every_render_does_not_raise() -> None:
    shadow = update_shadow(calls_hooks(2), None, NO_LAYOUTS).tree
    shadow = update_shadow(calls_hooks(2), shadow, NO_LAYOUTS).tree

    assert len(shadow.root.hooks.data) == 2


class RenderFailed(Exception):
    pass


@component
def raises_on_render(should_raise: bool) -> Text:
    use_state(0)
    if should_raise:
        raise RenderFailed()
    return Text(content="rendered")


@pytest.mark.parametrize("is_rerender", [False, True], ids=["mount", "rerender"])
def test_hook_context_is_restored_after_a_component_raises(is_rerender: bool) -> None:
    previous = update_shadow(raises_on_render(False), None, NO_LAYOUTS).tree if is_rerender else None
    outer_hooks = Hooks()
    outer_hook_idx = 5
    state_token = current_hook_state.set(outer_hooks)
    idx_token = current_hook_idx.set(outer_hook_idx)
    try:
        with pytest.raises(RenderFailed):
            update_shadow(raises_on_render(True), previous, NO_LAYOUTS).tree
        context_after_raise = (current_hook_state.get() is outer_hooks, current_hook_idx.get())
    finally:
        current_hook_idx.reset(idx_token)
        current_hook_state.reset(state_token)

    assert context_after_raise == (True, outer_hook_idx)
