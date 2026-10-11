"""
Render every docs screenshot in one process.

Run from the repository root as `uv run python -m docs.examples.generate_screenshots [module ...]`;
naming modules (such as `box_model`) renders only their screenshots.
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

import docs.examples
from counterweight.app import app
from counterweight.controls import Quit, Screenshot
from counterweight.output import Frame
from docs.examples.screenshot_spec import ASSETS, ScreenshotSpec

NOT_EXAMPLES = {"generate_screenshots", "screenshot_spec"}


def example_modules() -> list[str]:
    """Every module in `docs.examples` that holds examples rather than tooling."""
    return sorted(m.name for m in pkgutil.iter_modules(docs.examples.__path__) if m.name not in NOT_EXAMPLES)


def screenshots(module_name: str) -> list[ScreenshotSpec]:
    """The `SCREENSHOTS` an example module declares; every example module must declare them."""
    module = importlib.import_module(f"docs.examples.{module_name}")
    specs: list[ScreenshotSpec] = module.SCREENSHOTS
    return specs


async def render(spec: ScreenshotSpec) -> None:
    """Run the example headless and write its screenshot as SVG and as plain text."""
    await app(
        spec.root,
        headless=True,
        dimensions=spec.dimensions,
        autopilot=[*spec.events, Screenshot(handler=functools.partial(write_files, spec)), Quit()],
    )


def write_files(spec: ScreenshotSpec, frame: Frame) -> None:
    """Write the frame as SVG, and as plain text to copy from in the docs and to diff readably."""
    spec.svg_path.write_text(frame.svg() + "\n")
    spec.text_path.write_text(frame.text(ansi=False) + "\n")


def check_assets(specs: list[ScreenshotSpec], all_modules: bool) -> None:
    """Fail on two specs writing one asset, and, when every module was collected, on assets no spec writes."""
    duplicates = [asset for asset, count in Counter(spec.asset for spec in specs).items() if count > 1]
    if duplicates:
        raise ValueError(f"Several screenshots write the same assets: {duplicates}")
    if not all_modules:
        return
    written = {path for spec in specs for path in (spec.svg_path, spec.text_path)}
    orphans = sorted({*ASSETS.glob("*.svg"), *ASSETS.glob("*.txt")} - written)
    if orphans:
        raise ValueError(f"No example produces these assets: {[str(p) for p in orphans]}")


async def main(module_names: list[str]) -> None:
    specs = [spec for module_name in module_names or example_modules() for spec in screenshots(module_name)]
    check_assets(specs, all_modules=not module_names)
    new_paths = [path for spec in specs for path in (spec.svg_path, spec.text_path) if not path.exists()]
    for spec in specs:
        await render(spec)
    # pre-commit only fails a hook that leaves an unstaged diff, which a new untracked file isn't.
    if new_paths:
        subprocess.run(["git", "add", "--intent-to-add", *map(str, new_paths)], check=True)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
