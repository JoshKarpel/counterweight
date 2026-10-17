"""
The description of one docs screenshot, which each example module lists in its `SCREENSHOTS`,
and of one docs recording, which an example module may list in its `CASTS`.

`docs.examples.generate_screenshots` collects those lists and renders them.
"""

from collections.abc import Iterable
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from more_itertools import intersperse

from counterweight.autopilot import AutopilotStep
from counterweight.components import Component
from counterweight.controls import AdvanceClock

ASSETS = Path(__file__).parent.parent / "assets"


@dataclass(frozen=True, slots=True)
class ScreenshotSpec:
    """
    A headless render of `root` at `dimensions`, saved as `docs/assets/<asset>.svg`,
    with a plain-text copy beside it as `<asset>.txt`,
    which the docs show in a tab beside the image and which shows layout changes in a readable diff.

    `events` are fed to the app before the screenshot is taken,
    so one example can be shown in several states.
    The app's clock is frozen, so an `AdvanceClock` among them is the only way time passes
    that comes out the same on every run.
    """

    root: Component
    asset: str
    dimensions: tuple[int, int]
    events: Sequence[AutopilotStep] = ()

    @property
    def svg_path(self) -> Path:
        """Where the SVG is written."""
        return ASSETS / f"{self.asset}.svg"

    @property
    def text_path(self) -> Path:
        """Where the plain-text copy is written."""
        return ASSETS / f"{self.asset}.txt"


@dataclass(frozen=True, slots=True)
class CastSpec:
    """
    A headless recording of `root` at `dimensions` as `steps` drive it, saved as `docs/assets/<asset>.cast`,
    which a page plays where it has a `<!-- cast: <asset> -->` line.

    The app's clock is frozen, so the `AdvanceClock`s among `steps` are the time that passes in the recording,
    which comes out the same on every run as long as no step waits in real time.
    Its input is recorded too, so the player can show the keys as they're pressed.
    """

    root: Component
    asset: str
    dimensions: tuple[int, int]
    steps: Sequence[AutopilotStep]

    @property
    def cast_path(self) -> Path:
        """Where the recording is written."""
        return ASSETS / f"{self.asset}.cast"


def paced(
    steps: Iterable[AutopilotStep], every: timedelta, hold: timedelta = timedelta(seconds=2)
) -> list[AutopilotStep]:
    """
    `steps` with `every` passing before each one, as a person pauses between keys,
    and `hold` after the last, so a recording that loops lingers on where it ends.
    """
    gap = AdvanceClock(by=every)
    return [gap, *intersperse(gap, steps), AdvanceClock(by=hold)]
