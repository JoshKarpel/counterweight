from counterweight import app
from counterweight.components import component
from counterweight.controls import Quit
from counterweight.elements import Div
from counterweight.events import KeyPressed
from counterweight.geometry import Region
from counterweight.hooks import Rects, use_rects, use_state
from counterweight.styles.utilities import display_none, size

EMPTY = Region(left=0, top=0, right=0, bottom=0)
VISIBLE = Region(left=0, top=0, right=7, bottom=4)


@component
def measured(is_hidden: bool, recorded: list[Rects]) -> Div:
    recorded.append(use_rects())
    return Div(style=(size(7, 4) | display_none) if is_hidden else size(7, 4))


async def test_use_rects_reports_the_previous_frames_layout_and_empty_regions_once_hidden() -> None:
    recorded: list[Rects] = []

    @component
    def root() -> Div:
        is_hidden, set_is_hidden = use_state(False)
        renders, set_renders = use_state(0)

        def on_key(event: KeyPressed) -> None:
            match event.key:
                case "h":
                    set_is_hidden(True)
                case _:
                    set_renders(renders + 1)

        return Div(children=[measured(is_hidden, recorded)], on_key=on_key)

    await app(
        root(),
        headless=True,
        dimensions=(20, 10),
        autopilot=(KeyPressed(key="h"), KeyPressed(key="x"), Quit()),
    )

    # The warmup render, the first painted frame, the frame that hides it, and the frame after.
    assert [rects.border for rects in recorded] == [EMPTY, VISIBLE, VISIBLE, EMPTY]
