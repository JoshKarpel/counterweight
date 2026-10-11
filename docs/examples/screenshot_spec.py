"""
The description of one docs screenshot, which each example module lists in its `SCREENSHOTS`.

`docs.examples.generate_screenshots` collects those lists and renders them.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from counterweight.components import Component
from counterweight.controls import AnyControl
from counterweight.events import AnyEvent

ASSETS = Path(__file__).parent.parent / "assets"


@dataclass(frozen=True, slots=True)
class ScreenshotSpec:
    """
    A headless render of `root` at `dimensions`, saved as `docs/assets/<asset>.svg`,
    with a plain-text copy beside it as `<asset>.txt`,
    which the docs show in a tab beside the image and which shows layout changes in a readable diff.

    `events` are fed to the app before the screenshot is taken,
    so one example can be shown in several states.
    """

    root: Callable[[], Component]
    asset: str
    dimensions: tuple[int, int]
    events: Sequence[AnyEvent | AnyControl] = ()

    @property
    def svg_path(self) -> Path:
        """Where the SVG is written."""
        return ASSETS / f"{self.asset}.svg"

    @property
    def text_path(self) -> Path:
        """Where the plain-text copy is written."""
        return ASSETS / f"{self.asset}.txt"
