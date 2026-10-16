"""
Render every docs screenshot and recording in one process.

Run from the repository root as `uv run python -m docs.examples.generate_screenshots [module ...]`;
naming modules (such as `box_model`) renders only their screenshots and recordings.
Each render takes milliseconds, while a fresh interpreter takes hundreds,
so everything runs here rather than one process per example.
"""

import asyncio
import functools
import importlib
import pkgutil
import subprocess
import sys
from collections import Counter
from contextlib import suppress
from datetime import UTC
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import docs.examples
from counterweight.app import app
from counterweight.asciicast import Recording
from counterweight.clock import frozen_clock
from counterweight.controls import Quit
from counterweight.controls import Screenshot
from counterweight.output import Frame
from docs.examples.screenshot_spec import ASSETS
from docs.examples.screenshot_spec import CastSpec
from docs.examples.screenshot_spec import ScreenshotSpec

NOT_EXAMPLES = {"generate_screenshots", "screenshot_spec"}

# Every screenshot is taken, and every recording starts, at this time,
# so a screenshot of a clock doesn't change with each run.
SCREENSHOT_TIME = datetime(2026, 3, 14, 15, 9, 26, tzinfo=UTC)


def example_modules() -> list[str]:
    """Every module in `docs.examples` that holds examples rather than tooling."""
    return sorted(m.name for m in pkgutil.iter_modules(docs.examples.__path__) if m.name not in NOT_EXAMPLES)


def screenshots(module_name: str) -> list[ScreenshotSpec]:
    """The `SCREENSHOTS` an example module declares; every example module must declare them."""
    module = importlib.import_module(f"docs.examples.{module_name}")
    specs: list[ScreenshotSpec] = module.SCREENSHOTS
    return specs


def casts(module_name: str) -> list[CastSpec]:
    """The `CASTS` an example module declares, if it declares any."""
    module = importlib.import_module(f"docs.examples.{module_name}")
    specs: list[CastSpec] = getattr(module, "CASTS", [])
    return specs


async def render(spec: ScreenshotSpec) -> None:
    """
    Run the example headless at `SCREENSHOT_TIME`, checking its components are pure,
    and write its screenshot as SVG and as plain text.
    """
    await app(
        spec.root,
        headless=True,
        dimensions=spec.dimensions,
        autopilot=[*spec.events, Screenshot(handler=functools.partial(write_files, spec)), Quit()],
        check_purity=True,
        clock=frozen_clock(SCREENSHOT_TIME),
    )


async def record(spec: CastSpec) -> None:
    """
    Record the example headless from `SCREENSHOT_TIME`, checking its components are pure,
    into a scratch file that's copied over its recording only if it changed.
    """
    with TemporaryDirectory() as scratch:
        recorded = Path(scratch) / spec.cast_path.name
        await app(
            spec.root,
            headless=True,
            dimensions=spec.dimensions,
            autopilot=[*spec.steps, Quit()],
            check_purity=True,
            clock=frozen_clock(SCREENSHOT_TIME),
            recording=Recording(recorded, input=True),
        )
        write_if_changed(spec.cast_path, recorded.read_text())


def write_files(spec: ScreenshotSpec, frame: Frame) -> None:
    """Write the frame as SVG, and as plain text to copy from in the docs and to diff readably."""
    write_if_changed(spec.svg_path, frame.svg() + "\n")
    write_if_changed(spec.text_path, frame.text(ansi=False) + "\n")


def write_if_changed(path: Path, text: str) -> None:
    """
    Write `text` to `path` unless it already holds it,
    so an unchanged screenshot doesn't touch its file and restart `just docs-serve`, which watches them.
    """
    with suppress(FileNotFoundError):
        if path.read_text() == text:
            return
    path.write_text(text)


def written_paths(specs: list[ScreenshotSpec], cast_specs: list[CastSpec]) -> list[Path]:
    """Every file the screenshots and recordings write."""
    return [
        *(path for spec in specs for path in (spec.svg_path, spec.text_path)),
        *(spec.cast_path for spec in cast_specs),
    ]


def check_assets(specs: list[ScreenshotSpec], cast_specs: list[CastSpec], all_modules: bool) -> None:
    """Fail on two specs writing one asset, and, when every module was collected, on assets no spec writes."""
    duplicates = [path for path, count in Counter(written_paths(specs, cast_specs)).items() if count > 1]
    if duplicates:
        raise ValueError(f"Several screenshots or recordings write the same assets: {[str(p) for p in duplicates]}")
    if not all_modules:
        return
    written = set(written_paths(specs, cast_specs))
    orphans = sorted({*ASSETS.glob("*.svg"), *ASSETS.glob("*.txt"), *ASSETS.glob("*.cast")} - written)
    if orphans:
        raise ValueError(f"No example produces these assets: {[str(p) for p in orphans]}")


async def render_all(specs: list[ScreenshotSpec], cast_specs: list[CastSpec]) -> None:
    for spec in specs:
        await render(spec)
    for cast_spec in cast_specs:
        await record(cast_spec)


def main(module_names: list[str]) -> None:
    modules = module_names or example_modules()
    specs = [spec for module_name in modules for spec in screenshots(module_name)]
    cast_specs = [spec for module_name in modules for spec in casts(module_name)]
    check_assets(specs, cast_specs, all_modules=not module_names)
    new_paths = [path for path in written_paths(specs, cast_specs) if not path.exists()]
    asyncio.run(render_all(specs, cast_specs))
    # pre-commit only fails a hook that leaves an unstaged diff, which a new untracked file isn't.
    if new_paths:
        subprocess.run(["git", "add", "--intent-to-add", *map(str, new_paths)], check=True)


if __name__ == "__main__":
    main(sys.argv[1:])
