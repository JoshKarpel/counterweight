from __future__ import annotations

from collections.abc import Callable

import pytest

from counterweight.components import Component, component
from counterweight.elements import Div, Text
from counterweight.events import KeyPressed
from counterweight.hooks import Setter, use_memo, use_state
from counterweight.hooks.impls import StaleMemo, UseMemo
from counterweight.layout import NO_LAYOUTS
from counterweight.shadow import ShadowTree, update_shadow
from tests.rendering import state_set_keys, state_sets


def render_after_each(root: Component, steps: list[Callable[[], None]], check_purity: bool = False) -> list[ShadowTree]:
    """Renders `root`, then calls each step and renders again with the state it set, returning every tree."""
    with state_sets() as queue:
        trees = [update_shadow(root, None, NO_LAYOUTS).tree]
        for step in steps:
            step()
            trees.append(
                update_shadow(root, trees[-1], NO_LAYOUTS, state_set_keys(queue), check_purity=check_purity).tree
            )
        return trees


@component
def memoizes(deps: Callable[[int, int], tuple[object, ...]], log: list[object], setters: dict[str, Setter[int]]) -> Div:
    count, set_count = use_state(1)
    other, set_other = use_state(10)
    setters["count"] = set_count
    setters["other"] = set_other

    def compute() -> object:
        log.append(("compute", count))
        return object()

    log.append(use_memo(compute, deps(count, other)))
    return Div()


def step(setters: dict[str, Setter[int]], name: str) -> Callable[[], None]:
    return lambda: setters[name](lambda value: value + 1)


def test_equal_deps_return_the_same_object() -> None:
    log: list[object] = []
    setters: dict[str, Setter[int]] = {}

    render_after_each(memoizes(lambda count, other: (count,), log, setters), [step(setters, "other")])

    first, second = (entry for entry in log if not isinstance(entry, tuple))
    assert first is second


@pytest.mark.parametrize(
    ("deps", "expected"),
    [
        pytest.param(lambda count, other: (count,), [("compute", 1), ("compute", 2), ("compute", 3)], id="changed"),
        pytest.param(lambda count, other: (other,), [("compute", 1)], id="unchanged"),
        pytest.param(lambda count, other: (), [("compute", 1)], id="empty"),
    ],
)
def test_compute_runs_on_mount_and_whenever_deps_change(
    deps: Callable[[int, int], tuple[object, ...]], expected: list[tuple[str, int]]
) -> None:
    log: list[object] = []
    setters: dict[str, Setter[int]] = {}

    render_after_each(memoizes(deps, log, setters), [step(setters, "count"), step(setters, "count")])

    assert [entry for entry in log if isinstance(entry, tuple)] == expected


def test_compute_doesnt_run_again_once_changed_deps_stop_changing() -> None:
    log: list[object] = []
    setters: dict[str, Setter[int]] = {}

    render_after_each(
        memoizes(lambda count, other: (count,), log, setters), [step(setters, "count"), step(setters, "other")]
    )

    assert [entry for entry in log if isinstance(entry, tuple)] == [("compute", 1), ("compute", 2)]


@component
def caches_its_element(calls: list[str], setters: dict[str, Setter[int]]) -> Div:
    _, set_count = use_state(1)
    setters["parent"] = set_count
    calls.append("parent")

    @component
    def child() -> Text:
        calls.append("child")
        return Text(content="child")

    return use_memo(lambda: Div(children=[child()]), deps=())


def test_component_returning_a_cached_element_does_not_rerun_the_components_below_it() -> None:
    calls: list[str] = []
    setters: dict[str, Setter[int]] = {}

    render_after_each(caches_its_element(calls, setters), [step(setters, "parent")])

    assert calls == ["parent", "child", "parent"]


SETTINGS = {"label": "before"}


@component
def reads_setting(setters: dict[str, Setter[int]]) -> Text:
    _, set_count = use_state(1)
    setters["count"] = set_count
    return Text(content=use_memo(lambda: SETTINGS["label"], deps=()))


@component
def caches_handler(deps: Callable[[int, int], tuple[object, ...]], setters: dict[str, Setter[int]]) -> Text:
    count, set_count = use_state(1)
    other, set_other = use_state(10)
    setters["count"] = set_count
    setters["other"] = set_other

    def on_key(_: KeyPressed) -> None:
        print(count)

    return Text(content="", on_key=use_memo(lambda: on_key, deps(count, other)))


@pytest.mark.parametrize(
    "root",
    [
        pytest.param(reads_setting, id="reads-a-module-level-value"),
        pytest.param(lambda setters: caches_handler(lambda count, other: (), setters), id="captured-state"),
    ],
)
def test_check_purity_raises_naming_the_component_when_a_cached_value_is_missing_a_dependency(
    root: Callable[[dict[str, Setter[int]]], Component], monkeypatch: pytest.MonkeyPatch
) -> None:
    setters: dict[str, Setter[int]] = {}

    def change() -> None:
        monkeypatch.setitem(SETTINGS, "label", "after")
        step(setters, "count")()

    component = root(setters)
    with pytest.raises(StaleMemo, match=component.func.__qualname__):
        render_after_each(component, [change], check_purity=True)


def test_check_purity_keeps_a_cached_handler_whose_deps_are_complete() -> None:
    setters: dict[str, Setter[int]] = {}

    first, second = render_after_each(
        caches_handler(lambda count, other: (count,), setters), [step(setters, "other")], check_purity=True
    )

    assert second.root.element.on_key is first.root.element.on_key


@component(memo=True)
def deps_read_setting(argument: object) -> Text:
    use_memo(lambda: "constant", deps=(SETTINGS["label"],))
    return Text(content="")


@component
def holds_memo_child(setters: dict[str, Setter[int]]) -> Div:
    _, set_count = use_state(1)
    setters["parent"] = set_count
    return Div(children=[deps_read_setting("same")])


def test_check_purity_leaves_a_reused_components_memo_hooks_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    setters: dict[str, Setter[int]] = {}

    def change() -> None:
        monkeypatch.setitem(SETTINGS, "label", "after")
        step(setters, "parent")()

    _, second = render_after_each(holds_memo_child(setters), [change], check_purity=True)

    assert [hook.deps for hook in second.root.children[0].hooks.data if isinstance(hook, UseMemo)] == [("before",)]
