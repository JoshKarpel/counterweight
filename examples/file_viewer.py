from __future__ import annotations

import asyncio
import pathlib
import subprocess

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import AnyControl, Quit, StopPropagation
from counterweight.elements import Div, Text
from counterweight.events import KeyPressed, MouseDown, MouseEvent, MouseScrolledDown, MouseScrolledUp
from counterweight.hooks import Setter, use_effect, use_scroll, use_state
from counterweight.keys import Key
from counterweight.styles.utilities import *

# (depth, path, is_dir) — is_dir precomputed so renders don't make stat calls
TreeEntry = tuple[int, pathlib.Path, bool]


def _read_path(path: pathlib.Path) -> str:
    if path.is_dir():
        return f"[directory: {path}]"
    try:
        return path.read_text(errors="replace")
    except OSError as e:
        return f"[error: {e}]"


def _build_tree(root: pathlib.Path) -> list[TreeEntry]:
    """Return a flat list of (depth, path, is_dir) for files/dirs under root, respecting .gitignore if in a git repo."""
    visible: set[pathlib.Path] | None = None
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0:
            visible = set()
            for line in result.stdout.splitlines():
                p = root / line.strip()
                visible.add(p)
                for ancestor in p.parents:
                    if ancestor == root:
                        break
                    visible.add(ancestor)
    except Exception:
        pass

    entries: list[TreeEntry] = []

    def walk(path: pathlib.Path, depth: int) -> None:
        is_dir = path.is_dir()
        entries.append((depth, path, is_dir))
        if is_dir:
            try:
                children = sorted(
                    (c for c in path.iterdir() if visible is None or c in visible),
                    key=lambda p: (p.is_file(), p.name),
                )
            except PermissionError:
                return
            for child in children:
                walk(child, depth + 1)

    try:
        top_level = sorted(
            (c for c in root.iterdir() if visible is None or c in visible),
            key=lambda p: (p.is_file(), p.name),
        )
    except PermissionError:
        return entries

    for child in top_level:
        walk(child, 0)
    return entries


@component
def root() -> Div:
    base = pathlib.Path.cwd()
    tree: list[TreeEntry]
    tree, set_tree = use_state(list[TreeEntry])
    selected_idx, set_selected_idx = use_state(0)
    focused_pane, set_focused_pane = use_state("tree")

    async def load_tree() -> None:
        loaded = await asyncio.to_thread(_build_tree, base)
        set_tree(loaded)

    use_effect(load_tree, deps=())

    selected_path = tree[selected_idx][1] if tree else base

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
                style=row | grow(1) | min_height(0) | align_children_stretch,
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
                content="tab: switch  ·  ↑/↓: navigate  ·  arrows/scroll: scroll  ·  ctrl+c: quit",
                style=text_justify_center | text_color("slate", 500) | pad_y(1),
            ),
        ],
    )


@component
def tree_pane(
    tree: list[TreeEntry],
    selected_idx: int,
    set_selected_idx: Setter[int],
    focused: bool,
    set_focused_pane: Setter[str],
) -> Div:
    _scroll_state, scroll_style, _scroll_on_mouse, scroll_on_key = use_scroll(
        scroll_y=True, auto_scroll_to_y=selected_idx
    )

    # Cache formatted lines — only rebuild when tree identity or selection changes.
    # is_dir is precomputed in each TreeEntry so no stat calls happen here.
    lines_cache, set_lines_cache = use_state(lambda: (tree, selected_idx, ""))
    cached_tree, cached_idx, lines_text = lines_cache
    if tree is not cached_tree or selected_idx != cached_idx:
        lines = []
        for i, (depth, path, is_dir) in enumerate(tree):
            prefix = "  " * depth + ("▸ " if is_dir else "  ")
            marker = "● " if i == selected_idx else "  "
            name = path.name + ("/" if is_dir else "")
            lines.append(f"{marker}{prefix}{name}")
        lines_text = "\n".join(lines)
        set_lines_cache((tree, selected_idx, lines_text))

    def on_key(event: KeyPressed) -> AnyControl | None:
        match event.key:
            case Key.Down:
                set_selected_idx(lambda i: min(i + 1, max(len(tree) - 1, 0)))
                return None
            case Key.Up:
                set_selected_idx(lambda i: max(i - 1, 0))
                return None
        return scroll_on_key(event)

    def on_mouse(event: MouseEvent) -> AnyControl | None:
        if isinstance(event, MouseDown):
            set_focused_pane("tree")
        if isinstance(event, MouseScrolledDown):
            set_selected_idx(lambda i: min(i + 1, max(len(tree) - 1, 0)))
            return StopPropagation()
        elif isinstance(event, MouseScrolledUp):
            set_selected_idx(lambda i: max(i - 1, 0))
            return StopPropagation()
        return None

    border_col = border_color("sky", 600) if focused else border_color("slate", 700)

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
                content=lines_text,
                style=text_wrap_none,
            ),
        ],
    )


@component
def content_pane(
    path: pathlib.Path,
    focused: bool,
    set_focused_pane: Setter[str],
) -> Div:
    _scroll_state, scroll_style, scroll_on_mouse, scroll_on_key = use_scroll(
        scroll_x=True, scroll_y=True, reset_on=path
    )

    body_cache, set_body_cache = use_state(lambda: (path, _read_path(path)))
    if body_cache[0] != path:
        body = _read_path(path)
        set_body_cache((path, body))
    else:
        body = body_cache[1]

    def on_mouse(event: MouseEvent) -> AnyControl | None:
        if isinstance(event, MouseDown):
            set_focused_pane("content")
        return scroll_on_mouse(event)

    border_col = border_color("sky", 600) if focused else border_color("slate", 700)

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
                style=text_wrap_none,
            ),
        ],
    )


if __name__ == "__main__":
    asyncio.run(app(root))
