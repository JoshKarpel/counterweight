import asyncio
from datetime import timedelta

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import Bell
from counterweight.controls import Quit
from counterweight.controls import RestoreTitle
from counterweight.controls import SetTitle
from counterweight.controls import Suspend
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.programs import Edited
from counterweight.programs import EditOutcome
from counterweight.styles.utilities import *
from counterweight.widgets import text_input
from docs.examples.screenshot_spec import CastSpec
from docs.examples.screenshot_spec import ScreenshotSpec
from docs.examples.screenshot_spec import paced

# --8<-- [start:example]


@component
def title_editor() -> Div:
    draft, set_draft = use_state("")
    title, set_title = use_state("")

    def edited(outcome: EditOutcome) -> None:
        match outcome:
            case Edited(text=text):
                set_draft(text.strip())
            case _:
                pass

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.Enter):
                if not draft:
                    return Bell()
                set_title(draft)
                return SetTitle(draft)
            case KeyPressed(key=Key.Escape):
                set_title("")
                return RestoreTitle()
            case KeyPressed(key=Key.ControlO):
                return Suspend.to_edit_text(draft, on_edit=edited)
            case KeyPressed(key=Key.ControlQ):
                return Quit()
            case _:
                return None

    return Div(
        style=col | width(60),
        on_input=on_input,
        children=(
            text_input(draft, set_draft, placeholder="Window title", auto_focus=True),
            Text(content=f"Window title: {title or "the terminal's own"}"),
            Text(
                content="Enter: set · Escape: restore · Ctrl+O: edit · Ctrl+Q: quit",
                style=text_color("slate", 400),
            ),
        ),
    )


# --8<-- [end:example]


def typed(text: str) -> tuple[KeyPressed, ...]:
    return tuple(KeyPressed(key=character) for character in text)


DIMENSIONS = (62, 6)
ENTER = KeyPressed(key=Key.Enter)
SET = (*typed("Build logs"), ENTER)

SCREENSHOTS = [
    ScreenshotSpec(title_editor(), "input-controls-title", DIMENSIONS, events=SET),
]

CASTS = [
    CastSpec(
        title_editor(),
        "input-controls-title",
        DIMENSIONS,
        steps=paced([ENTER, *SET, KeyPressed(key=Key.Escape)], every=timedelta(milliseconds=300)),
    )
]


if __name__ == "__main__":
    asyncio.run(app(title_editor()))
