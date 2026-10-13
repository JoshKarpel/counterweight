from counterweight import app
from counterweight.components import component
from counterweight.controls import Quit
from counterweight.elements import Div
from counterweight.events import InputEvent, KeyPressed, Receiver
from counterweight.geometry import Region
from counterweight.hooks import Rects, use_rects, use_state
from counterweight.styles.utilities import border, display_none, margin, pad, size

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

        def on_input(event: InputEvent, _: Receiver) -> None:
            match event:
                case KeyPressed(key="h"):
                    set_is_hidden(True)
                case _:
                    set_renders(renders + 1)

        return Div(children=[measured(is_hidden, recorded)], on_input=on_input)

    await app(
        root(),
        headless=True,
        dimensions=(20, 10),
        autopilot=(KeyPressed(key="h"), KeyPressed(key="x"), Quit()),
    )

    # The warmup render, the first painted frame, the frame that hides it, and the frame after.
    assert [rects.border for rects in recorded] == [EMPTY, VISIBLE, VISIBLE, EMPTY]


NESTED_BOXES = Rects(
    content=Region(left=3, top=3, right=8, bottom=6),
    padding=Region(left=2, top=2, right=9, bottom=7),
    border=Region(left=1, top=1, right=10, bottom=8),
    margin=Region(left=0, top=0, right=11, bottom=9),
)


async def test_use_rects_reports_each_box_and_the_purity_check_rereads_them() -> None:
    recorded: list[Rects] = []

    @component
    def boxed() -> Div:
        recorded.append(use_rects())
        return Div(style=margin(1) | border | pad(1) | size(9, 7))

    await app(boxed(), headless=True, dimensions=(20, 10), autopilot=(Quit(),), check_purity=True)

    # The painted frame's render, then the purity check's re-run of it.
    assert recorded[-2:] == [NESTED_BOXES, NESTED_BOXES]
