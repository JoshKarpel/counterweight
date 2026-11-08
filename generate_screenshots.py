"""
Render every docs screenshot and recording in one process.

Run from the repository root as `uv run python -m docs.generate_screenshots [example ...]`;
naming examples (such as `box-model` or `chat`) renders only their stills and demos.
Each render takes milliseconds, while a fresh interpreter takes hundreds,
so everything runs here rather than one process per example.
"""

import asyncio
import subprocess
import sys
from collections import Counter
from contextlib import suppress
from pathlib import Path

from counterweight.examples import gallery
from counterweight.examples.catalog import Example
from counterweight.examples.catalog import examples
from counterweight.examples.scenes import Demo
from counterweight.examples.scenes import Still
from counterweight.examples.scenes import frame_of
from counterweight.examples.scenes import recording_of

ASSETS = Path(__file__).parent / "assets"


def chosen(names: list[str]) -> list[Example]:
    """The examples named, by their names (`box-model`) or their modules' (`box_model`), or every one for none."""
    catalog = examples()
    if not names:
        return list(catalog)
    wanted = {name.replace("_", "-") for name in names}
    unknown = wanted - {example.name for example in catalog}
    if unknown:
        raise ValueError(f"There are no examples named {sorted(unknown)}")
    return [example for example in catalog if example.name in wanted]


def svg_path(still: Still) -> Path:
    """Where a still's SVG goes, which the docs show."""
    return ASSETS / f"{still.name}.svg"


def text_path(still: Still) -> Path:
    """Where the plain-text copy of a still goes, which the docs show beside it and which diffs readably."""
    return ASSETS / f"{still.name}.txt"


def cast_path(demo: Demo) -> Path:
    """Where a demo's recording goes, which a page plays where it has a `<!-- cast: <name> -->` line."""
    return ASSETS / f"{demo.name}.cast"


async def render(still: Still) -> None:
    """Write the still as SVG, and as plain text to copy from in the docs and to diff readably."""
    frame = await frame_of(still)
    write_if_changed(svg_path(still), frame.svg() + "\n")
    write_if_changed(text_path(still), frame.text(ansi=False) + "\n")


async def record(demo: Demo) -> None:
    """Write the demo's recording, touching the file only if it changed."""
    write_if_changed(cast_path(demo), await recording_of(demo))


def write_if_changed(path: Path, text: str) -> None:
    """
    Write `text` to `path` unless it already holds it,
    so an unchanged screenshot doesn't touch its file and restart `just docs-serve`, which watches them.
    """
    with suppress(FileNotFoundError):
        if path.read_text() == text:
            return
    path.write_text(text)


def written_paths(all_stills: list[Still], all_demos: list[Demo]) -> list[Path]:
    """Every file the stills and demos write."""
    return [
        *(path for still in all_stills for path in (svg_path(still), text_path(still))),
        *(cast_path(demo) for demo in all_demos),
    ]


def check_assets(all_stills: list[Still], all_demos: list[Demo], all_modules: bool) -> None:
    """Fail on two scenes writing one asset, and, when every module was collected, on assets no scene writes."""
    duplicates = [path for path, count in Counter(written_paths(all_stills, all_demos)).items() if count > 1]
    if duplicates:
        raise ValueError(f"Several stills or demos write the same assets: {[str(p) for p in duplicates]}")
    if not all_modules:
        return
    written = set(written_paths(all_stills, all_demos))
    orphans = sorted({*ASSETS.glob("*.svg"), *ASSETS.glob("*.txt"), *ASSETS.glob("*.cast")} - written)
    if orphans:
        raise ValueError(f"No example produces these assets: {[str(p) for p in orphans]}")


async def render_all(all_stills: list[Still], all_demos: list[Demo]) -> None:
    for still in all_stills:
        await render(still)
    for demo in all_demos:
        await record(demo)


def main(names: list[str]) -> None:
    # The gallery isn't an example, so the catalog doesn't list it.
    named = [name for name in names if name != "gallery"]
    # Naming only the gallery renders only it, where naming nothing renders everything.
    chosen_examples = [] if names and not named else chosen(named)
    with_gallery = not names or "gallery" in names
    all_stills = [
        *(still for example in chosen_examples for still in example.stills),
        *(gallery.STILLS if with_gallery else ()),
    ]
    all_demos = [
        *(demo for example in chosen_examples for demo in example.demos),
        *(gallery.DEMOS if with_gallery else ()),
    ]
    check_assets(all_stills, all_demos, all_modules=not names)
    new_paths = [path for path in written_paths(all_stills, all_demos) if not path.exists()]
    asyncio.run(render_all(all_stills, all_demos))
    # pre-commit only fails a hook that leaves an unstaged diff, which a new untracked file isn't.
    if new_paths:
        subprocess.run(["git", "add", "--intent-to-add", *map(str, new_paths)], check=True)


if __name__ == "__main__":
    main(sys.argv[1:])
