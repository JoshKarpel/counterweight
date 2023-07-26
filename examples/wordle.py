import asyncio
from random import choice
from string import ascii_letters
from textwrap import dedent
from typing import Literal

from more_itertools import padded
from structlog import get_logger

from reprisal.app import app
from reprisal.components import Div, Text, component
from reprisal.events import KeyPressed
from reprisal.hooks import use_state
from reprisal.keys import Key
from reprisal.styles.utilities import *

logger = get_logger()

blank = " " * 5

SOLUTIONS = [
    "heart",
    "opera",
    "sugar",
]


@component
def root() -> Div:
    solution, set_solution = use_state(choice(SOLUTIONS).upper())

    guess, set_guess = use_state("")
    submitted, set_submitted = use_state([])

    state = "win" if submitted and submitted[-1] == solution else "playing" if len(submitted) < 5 else "loss"

    def on_key(event: KeyPressed) -> None:
        match state, event.key:
            case _, Key.Delete:
                set_guess("")
                set_submitted([])
                set_solution(choice(SOLUTIONS).upper())
            case "playing", Key.Backspace:
                if len(guess) > 0:
                    set_guess(guess[:-1])
                else:
                    pass  # TODO: bell
            case "playing", Key.Enter:
                if len(guess) == 5 and len(submitted) < 5:
                    set_guess("")
                    set_submitted(lambda s: [*s, guess])
                else:
                    pass  # TODO: bell
            case "playing", letter if letter in ascii_letters:
                if len(guess) < 5:
                    set_guess(lambda g: g + letter.upper())
                else:
                    pass  # TODO: bell

    return Div(
        style=col | align_children_center,
        on_key=on_key,
        children=[
            Div(
                style=row | weight_none,
                children=[
                    Text(
                        content="Wordle",
                        style=text_amber_600,
                    )
                ],
            ),
            Div(
                style=col
                | justify_children_center
                | align_self_stretch
                | align_children_stretch
                | gap_children_1
                | border_lightrounded,
                children=[
                    *(guess_row(s, solution=solution, type="submitted") for s in submitted),
                    guess_row(guess, solution=solution, type="current")
                    if state == "playing"
                    else guess_row(blank, solution=solution, type="pending"),
                    *(guess_row(blank, solution=solution, type="pending") for _ in range(5 - len(submitted) - 1)),
                ],
            ),
            Div(
                style=row | weight_none | border_lightrounded,
                children=[
                    Text(
                        content=f"{state}!",
                        style=weight_none | text_slate_200 | border_lightrounded | pad_x_1 | pad_y_0,
                    )
                ],
            ),
            Div(
                style=row | weight_none | align_children_end,
                children=[
                    Text(
                        content=dedent(
                            """\
                            - it's wordle
                            """
                        ),
                        style=border_slate_400 | text_slate_200 | border_lightrounded | pad_x_1 | pad_y_0,
                    ),
                ],
            ),
        ],
    )


@component
def guess_row(guess: str, solution: str, type: Literal["submitted", "current", "pending"]) -> Div:
    children = []
    for guess_letter, solution_letter in zip(padded(guess, fillvalue=" ", n=5), solution):
        style = {
            "submitted": border_double,
            "current": border_heavy,
            "pending": border_double,
        }[type]

        if type == "submitted":
            if guess_letter == solution_letter:
                style |= border_green_600
            elif guess_letter in solution:
                style |= border_yellow_300
            else:
                style |= border_red_700
        elif type == "pending":
            style |= border_gray_700
        elif type == "current":
            style |= border_gray_300 if guess_letter != " " else border_gray_500

        children.append(
            letter_box(
                guess_letter,
                style=style,
            )
        )

    return Div(
        style=row | weight_none | justify_children_center | align_children_center | gap_children_1,
        children=children,
    )


@component
def letter_box(letter: str, style: Style) -> Text:
    return Text(
        content=letter,
        style=style | weight_none | border_light | pad_x_1 | pad_y_0,
    )


asyncio.run(app(root))
