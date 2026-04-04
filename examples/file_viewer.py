from __future__ import annotations

import pathlib

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import AnyControl, Quit
from counterweight.elements import Div, Text
from counterweight.events import KeyPressed, MouseDown, MouseEvent
from counterweight.hooks import Setter, use_scroll, use_state
from counterweight.keys import Key
from counterweight.styles.utilities import *


def _build_tree(root: pathlib.Path) -> list[tuple[int, pathlib.Path]]:
    """Return a flat list of (depth, path) for all files/dirs under root, sorted."""
    entries: list[tuple[int, pathlib.Path]] = []

    def walk(path: pathlib.Path, depth: int) -> None:
        entries.append((depth, path))
        if path.is_dir():
            for child in sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name)):
                walk(child, depth + 1)

    for child in sorted(root.iterdir(), key=lambda p: (p.is_file(), p.name)):
        walk(child, 0)
    return entries


@component
def root() -> Div:
    base = pathlib.Path.cwd()
    tree, _ = use_state(lambda: _build_tree(base))
    selected_idx, set_selected_idx = use_state(0)
    focused_pane, set_focused_pane = use_state("tree")

    _depth, selected_path = tree[selected_idx]

    def on_key(event: KeyPressed) -> AnyControl | None:
        match event.key:
            case Key.ControlC:
                return Quit()
            case Key.Tab:
                set_focused_pane(lambda p: "content" if p == "tree" else "tree")
        return None

    return Div(
        style=col | full | align_children_stretch,
        on_key=on_key,
        children=[
            Div(
                style=row | grow(1) | align_children_stretch,
                children=[
                    tree_pane(
                        tree,
                        selected_idx,
                        set_selected_idx,
                        focused_pane == "tree",
                        set_focused_pane,
                    ),
                    content_pane(
                        selected_path,
                        focused_pane == "content",
                        set_focused_pane,
                    ),
                ],
            ),
            Text(
                content="tab: switch pane  ·  ↑/↓: navigate tree  ·  scroll/arrows: scroll content  ·  ctrl+c: quit",
                style=text_justify_center | text_color("slate", 500) | pad_y(1),
            ),
        ],
    )


@component
def tree_pane(
    tree: list[tuple[int, pathlib.Path]],
    selected_idx: int,
    set_selected_idx: Setter[int],
    focused: bool,
    set_focused_pane: Setter[str],
) -> Div:
    _scroll_state, scroll_style, scroll_on_mouse, scroll_on_key = use_scroll(scroll_y=True)

    def on_key(event: KeyPressed) -> AnyControl | None:
        match event.key:
            case Key.Down:
                set_selected_idx(lambda i: min(i + 1, len(tree) - 1))
                return None
            case Key.Up:
                set_selected_idx(lambda i: max(i - 1, 0))
                return None
        return scroll_on_key(event)

    def on_mouse(event: MouseEvent) -> AnyControl | None:
        if isinstance(event, MouseDown):
            set_focused_pane("tree")
        return scroll_on_mouse(event)

    border_col = border_color("sky", 600) if focused else border_color("slate", 700)

    lines = []
    for i, (depth, path) in enumerate(tree):
        prefix = "  " * depth + ("▸ " if path.is_dir() else "  ")
        marker = "● " if i == selected_idx else "  "
        name = path.name + ("/" if path.is_dir() else "")
        lines.append(f"{marker}{prefix}{name}")

    return Div(
        style=width(30) | col | align_children_stretch | border_lightrounded | border_col | scroll_style,
        on_mouse=on_mouse,
        on_key=on_key if focused else None,
        children=[
            Text(
                content=" Files ",
                style=position_absolute | inset_top(-1) | inset_left(2) | border_col,
            ),
            Text(
                content="\n".join(lines),
                style=grow(1) | text_wrap_none,
            ),
        ],
    )


@component
def content_pane(
    path: pathlib.Path,
    focused: bool,
    set_focused_pane: Setter[str],
) -> Div:
    _scroll_state, scroll_style, scroll_on_mouse, scroll_on_key = use_scroll(scroll_x=True, scroll_y=True)

    def on_mouse(event: MouseEvent) -> AnyControl | None:
        if isinstance(event, MouseDown):
            set_focused_pane("content")
        return scroll_on_mouse(event)

    border_col = border_color("sky", 600) if focused else border_color("slate", 700)

    if path.is_dir():
        body = f"[directory: {path}]"
    else:
        try:
            body = path.read_text(errors="replace")
        except OSError as e:
            body = f"[error: {e}]"

    return Div(
        style=grow(1) | min_width(0) | col | align_children_stretch | border_lightrounded | border_col | scroll_style,
        on_mouse=on_mouse,
        on_key=scroll_on_key if focused else None,
        children=[
            Text(
                content=f" {path.name} ",
                style=position_absolute | inset_top(-1) | inset_left(2) | border_col,
            ),
            Text(
                content=body,
                style=grow(1) | text_wrap_none,
            ),
        ],
    )


if __name__ == "__main__":
    import asyncio

    asyncio.run(app(root))
