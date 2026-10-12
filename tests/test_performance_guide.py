"""
The claims `docs/performance.md` makes: what its examples re-run, and each failure mode's symptom and fix.
The failure modes' code mirrors the page's inline snippets, so a change that stops one failing breaks a test here.
"""

from __future__ import annotations

from asyncio import Queue
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace

import pytest

from counterweight.app import app
from counterweight.components import Component, component
from counterweight.controls import Quit
from counterweight.elements import AnyElement, Div, Text
from counterweight.events import AnyEvent, KeyPressed
from counterweight.hooks import Setter, use_memo, use_ref, use_state
from counterweight.hooks.impls import InconsistentHookExecution, StaleMemo, UseState
from counterweight.keys import Key
from counterweight.layout import NO_LAYOUTS
from counterweight.shadow import ImpureComponent, ShadowNode, ShadowTree, ShadowUpdate, update_shadow
from docs.examples import performance_process_table, performance_state_in_root, performance_state_moved_down
from docs.examples.performance_process_table import PROCESSES, Process, process_row, process_table
from tests.rendering import state_set_keys, state_sets


@dataclass(slots=True)
class Renders:
    """Renders as the render loop does: each render after the first gets the state set since the one before."""

    queue: Queue[AnyEvent]
    check_purity: bool
    tree: ShadowTree | None = None

    def render(self, root: Component | AnyElement) -> ShadowUpdate:
        update = update_shadow(root, self.tree, NO_LAYOUTS, state_set_keys(self.queue), check_purity=self.check_purity)
        self.tree = update.tree
        return update


@contextmanager
def renders(check_purity: bool = False) -> Iterator[Renders]:
    with state_sets() as queue:
        yield Renders(queue=queue, check_purity=check_purity)


def ran(update: ShadowUpdate) -> list[str]:
    """The components a render ran, by function name, with their key if they have one."""
    ran_hooks = {id(hooks) for hooks in update.ran}
    return [
        node.component.func.__name__
        if node.component.key is None
        else f"{node.component.func.__name__}:{node.component.key}"
        for node in update.tree.nodes
        if node.component is not None and id(node.hooks) in ran_hooks
    ]


def rows(names: list[str]) -> list[str]:
    return [name for name in names if name.startswith("process_row")]


def find(tree: ShadowNode, func: Callable[..., Component]) -> ShadowNode:
    return next(
        node for node in tree.walk() if node.component is not None and node.component.func.__name__ == func.__name__
    )


def setter_of(node: ShadowNode) -> Setter[object]:
    return next(hook.setter for hook in node.hooks.data if isinstance(hook, UseState))


def content(node: ShadowNode) -> object:
    match node.element:
        case Text(content=content):
            return content
        case _:
            return None


def press(node: ShadowNode, key: str) -> None:
    on_key = node.element.on_key
    assert on_key is not None
    on_key(KeyPressed(key=key))


# Which components run in a frame?


@pytest.mark.parametrize(
    ("root", "holder", "expected"),
    [
        pytest.param(
            performance_state_in_root.dashboard,
            performance_state_in_root.dashboard,
            ["dashboard", *["metric_card"] * 4],
            id="state-in-root",
        ),
        pytest.param(
            performance_state_moved_down.dashboard,
            performance_state_moved_down.uptime,
            ["uptime"],
            id="state-moved-down",
        ),
    ],
)
def test_the_uptime_ticking_reruns_the_component_holding_it_and_everything_it_returns(
    root: Callable[[], Component], holder: Callable[[], Component], expected: list[str]
) -> None:
    dashboard = root()
    with renders() as r:
        tree = r.render(dashboard).tree.root
        setter_of(find(tree, holder))(1)

        assert ran(r.render(dashboard)) == expected


# How do I skip a component whose arguments didn't change?


def test_moving_the_selection_reruns_only_the_two_rows_whose_selection_changed() -> None:
    root = process_table(PROCESSES)
    with renders() as r:
        press(r.render(root).tree.root, Key.Down)

        assert ran(r.render(root)) == ["process_table", "process_row:977", "process_row:2048"]


REDIS_BUSY = tuple(replace(process, cpu=50.0) if process.name == "redis" else process for process in PROCESSES)


def test_reordered_keyed_rows_rerun_only_the_row_whose_process_changed() -> None:
    with renders() as r:
        r.render(process_table(PROCESSES))

        assert ran(r.render(process_table(REDIS_BUSY))) == ["process_table", "process_row:3311"]


# What goes wrong? `memo=True`


@component
def process_table_with_inline_handler(processes: tuple[Process, ...]) -> Div:
    by_cpu = use_memo(lambda: sorted(processes, key=lambda process: process.cpu, reverse=True), deps=(processes,))
    selected_pid, set_selected_pid = use_state(by_cpu[0].pid)

    def on_key(event: KeyPressed) -> None:
        pids = [process.pid for process in by_cpu]
        set_selected_pid(pids[min(pids.index(selected_pid) + 1, len(pids) - 1)])

    return Div(
        on_key=on_key,
        children=[
            # The wrapping lambda is the mistake under test: a new object every render.
            process_row(
                process,
                process.pid == selected_pid,
                lambda pid: set_selected_pid(pid),  # noqa: PLW0108
            ).with_key(str(process.pid))
            for process in by_cpu
        ],
    )


def test_a_callback_argument_built_while_rendering_reruns_every_memo_row() -> None:
    root = process_table_with_inline_handler(PROCESSES)
    with renders() as r:
        press(r.render(root).tree.root, Key.Down)

        assert len(rows(ran(r.render(root)))) == len(PROCESSES)


@component
def unkeyed_process_table(processes: tuple[Process, ...]) -> Div:
    by_cpu = use_memo(lambda: sorted(processes, key=lambda process: process.cpu, reverse=True), deps=(processes,))
    selected_pid, set_selected_pid = use_state(by_cpu[0].pid)

    return Div(
        children=[process_row(process, process.pid == selected_pid, set_selected_pid) for process in by_cpu],
    )


def test_unkeyed_memo_rows_rerun_wherever_the_list_reordered() -> None:
    with renders() as r:
        r.render(unkeyed_process_table(PROCESSES))

        # Redis moves from fourth to first, so the first four rows each get a different process.
        assert len(rows(ran(r.render(unkeyed_process_table(REDIS_BUSY))))) == 4


@component(memo=True)
def key_list(keys: list[str]) -> Text:
    return Text(content=" ".join(keys))


@component
def key_log_mutating() -> Div:
    keys = use_ref(list[str]())
    count, set_count = use_state(0)

    def on_key(event: KeyPressed) -> None:
        keys.current.append(event.key)
        set_count(count + 1)

    return Div(on_key=on_key, children=[key_list(keys.current)])


@component(memo=True)
def key_tuple(keys: tuple[str, ...]) -> Text:
    return Text(content=" ".join(keys))


@component
def key_log_with_tuple() -> Div:
    keys, set_keys = use_state(tuple[str, ...]())

    def on_key(event: KeyPressed) -> None:
        set_keys((*keys, event.key))

    return Div(on_key=on_key, children=[key_tuple(keys)])


@pytest.mark.parametrize("check_purity", [False, True], ids=["stale", "check-purity"])
def test_an_argument_mutated_in_place_keeps_a_memo_component_stale(check_purity: bool) -> None:
    root = key_log_mutating()
    with renders(check_purity=check_purity) as r:
        press(r.render(root).tree.root, "a")

        if check_purity:
            with pytest.raises(ImpureComponent, match="key_list"):
                r.render(root)
        else:
            assert r.render(root).tree.root.children[0].element == Text(content="")


def test_an_argument_replaced_rather_than_mutated_reruns_its_memo_component() -> None:
    root = key_log_with_tuple()
    with renders(check_purity=True) as r:
        press(r.render(root).tree.root, "a")

        assert r.render(root).tree.root.children[0].element == Text(content="a")


SETTINGS = {"accent": "amber"}


@component(memo=True)
def title(text: str) -> Text:
    return Text(content=f"[{SETTINGS['accent']}] {text}")


@component(memo=True)
def title_with_accent(text: str, accent: str) -> Text:
    return Text(content=f"[{accent}] {text}")


@component
def page(use_argument: bool) -> Div:
    count, set_count = use_state(0)
    child = title_with_accent("Processes", SETTINGS["accent"]) if use_argument else title("Processes")
    return Div(on_key=lambda _: set_count(count + 1), children=[child, Text(content=str(count))])


@pytest.mark.parametrize(("use_argument", "is_stale"), [(False, True), (True, False)], ids=["hidden", "argument"])
def test_a_module_level_value_read_by_a_memo_component_goes_stale(
    use_argument: bool, is_stale: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = page(use_argument)
    with renders(check_purity=True) as r:
        tree = r.render(root).tree.root
        monkeypatch.setitem(SETTINGS, "accent", "cyan")
        press(tree, "a")

        if is_stale:
            with pytest.raises(ImpureComponent, match="title"):
                r.render(root)
        else:
            assert r.render(root).tree.root.children[0].element == Text(content="[cyan] Processes")


@dataclass(frozen=True, slots=True, eq=False)
class Line:
    """A line whose comparisons are counted, to see how much of an argument a `memo` component's hit compares."""

    text: str
    comparisons: list[str]

    def __eq__(self, other: object) -> bool:
        self.comparisons.append(self.text)
        return isinstance(other, Line) and self.text == other.text

    def __hash__(self) -> int:
        return hash(self.text)


@component(memo=True)
def line_list(lines: tuple[Line, ...]) -> Text:
    return Text(content="\n".join(line.text for line in lines))


@component
def log_view(lines: tuple[str, ...], comparisons: list[str], keep: bool) -> Div:
    count, set_count = use_state(0)

    def upper() -> tuple[Line, ...]:
        return tuple(Line(text=line.upper(), comparisons=comparisons) for line in lines)

    argument = use_memo(upper, deps=(lines,)) if keep else upper()
    return Div(on_key=lambda _: set_count(count + 1), children=[line_list(argument)])


@pytest.mark.parametrize(("keep", "expected"), [(False, 3), (True, 0)], ids=["rebuilt", "kept"])
def test_a_memo_hit_on_a_rebuilt_argument_compares_every_item(keep: bool, expected: int) -> None:
    comparisons: list[str] = []
    root = log_view(("a", "b", "c"), comparisons, keep)
    with renders() as r:
        press(r.render(root).tree.root, "x")
        update = r.render(root)

    assert (ran(update), len(comparisons)) == (["log_view"], expected)


# What goes wrong? `use_memo`


@component
def busy_count(processes: tuple[Process, ...], threshold: float) -> Text:
    busy = use_memo(lambda: [process for process in processes if process.cpu > threshold], deps=(processes,))
    return Text(content=f"{len(busy)} busy")


@component
def busy_count_with_threshold(processes: tuple[Process, ...], threshold: float) -> Text:
    busy = use_memo(lambda: [process for process in processes if process.cpu > threshold], deps=(processes, threshold))
    return Text(content=f"{len(busy)} busy")


@pytest.mark.parametrize(
    ("func", "is_stale"),
    [(busy_count, True), (busy_count_with_threshold, False)],
    ids=["missing-dependency", "complete"],
)
def test_a_dependency_missing_from_use_memo_keeps_its_value_stale(
    func: Callable[[tuple[Process, ...], float], Component], is_stale: bool
) -> None:
    with renders(check_purity=True) as r:
        r.render(func(PROCESSES, 10.0))

        if is_stale:
            with pytest.raises(StaleMemo, match=func.__name__):
                r.render(func(PROCESSES, 1.0))
        else:
            assert r.render(func(PROCESSES, 1.0)).tree.root.element == Text(content="4 busy")


@component
def counter_capturing() -> Text:
    count, set_count = use_state(0)
    on_key = use_memo(lambda: lambda _: set_count(count + 1), deps=())
    return Text(content=str(count), on_key=on_key)


@component
def counter() -> Text:
    count, set_count = use_state(0)
    on_key = use_memo(lambda: lambda _: set_count(lambda count: count + 1), deps=())
    return Text(content=str(count), on_key=on_key)


def test_a_cached_handler_that_captured_state_keeps_acting_on_it() -> None:
    root = counter_capturing()
    with renders() as r:
        tree = r.render(root).tree.root
        for _ in range(3):
            press(tree, "a")
            tree = r.render(root).tree.root

    assert content(tree) == "1"


def test_check_purity_raises_for_a_cached_handler_that_captured_state() -> None:
    root = counter_capturing()
    with renders(check_purity=True) as r:
        press(r.render(root).tree.root, "a")

        with pytest.raises(StaleMemo, match="counter_capturing"):
            r.render(root)


def test_a_cached_handler_with_a_functional_update_counts_every_press() -> None:
    root = counter()
    with renders(check_purity=True) as r:
        tree = r.render(root).tree.root
        for _ in range(3):
            press(tree, "a")
            tree = r.render(root).tree.root

    assert content(tree) == "3"


@component
def search(on_submit: Callable[[str], None], log: list[str]) -> Text:
    def submit() -> Callable[[KeyPressed], None]:
        log.append("compute")
        return lambda event: on_submit(event.key)

    return Text(content="", on_key=use_memo(submit, deps=(on_submit,)))


@component
def search_page(log: list[str], inline: bool) -> Div:
    query, set_query = use_state("")
    on_submit = (lambda text: set_query(text)) if inline else set_query  # noqa: PLW0108
    return Div(children=[search(on_submit, log), Text(content=query)])


@pytest.mark.parametrize(("inline", "expected"), [(True, 3), (False, 1)], ids=["inline", "setter"])
def test_a_dependency_built_every_render_recomputes_every_render(inline: bool, expected: int) -> None:
    log: list[str] = []
    root = search_page(log, inline)
    with renders() as r:
        tree = r.render(root).tree.root
        for key in "ab":
            press(tree.children[0], key)
            tree = r.render(root).tree.root

    assert len(log) == expected


@component
def process_labels(processes: tuple[Process, ...]) -> Div:
    labels = [use_memo(lambda: f"{process.name} ({process.pid})", deps=(process,)) for process in processes]
    return Div(children=[Text(content=label) for label in labels])


def test_use_memo_in_a_loop_raises_when_the_loop_length_changes() -> None:
    with renders() as r:
        r.render(process_labels(PROCESSES))

        with pytest.raises(InconsistentHookExecution):
            r.render(process_labels(PROCESSES[:3]))


# How do I catch stale output?


async def test_process_table_is_pure() -> None:
    await app(
        performance_process_table.root,
        headless=True,
        dimensions=(32, 7),
        autopilot=[KeyPressed(key=Key.Down), KeyPressed(key=Key.Down), KeyPressed(key=Key.Up), Quit()],
        check_purity=True,
    )
