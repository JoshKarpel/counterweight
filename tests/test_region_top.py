"""Where an inline region that tracks the mouse starts on the screen, from the terminal's answers and the frames since."""

from __future__ import annotations

import pytest

from counterweight._app import RegionMove
from counterweight._app import RegionTop
from counterweight._app import next_region_top


@pytest.mark.parametrize(
    ("top", "move", "expected"),
    [
        (2, (0, 3, 10), 2),
        (2, (4, 3, 10), 6),
        (5, (4, 3, 10), 7),
        (6, (0, 6, 10), 4),
        (6, (0, 2, 10), 6),
    ],
    ids=["unmoved", "printed above", "printed past the bottom", "grown past the bottom", "shrunk"],
)
def test_the_region_moves_down_by_what_is_printed_and_up_by_what_scrolls(
    top: int, move: RegionMove, expected: int
) -> None:
    assert next_region_top(top, move) == expected


def test_the_region_is_nowhere_until_the_terminal_answers() -> None:
    assert RegionTop().asked().moved((1, 2, 10)).top is None


def test_an_answer_is_moved_by_the_frames_written_since_the_request() -> None:
    assert RegionTop().asked().moved((3, 2, 10)).moved((1, 4, 10)).answered(4) == RegionTop(top=6)


def test_only_the_answer_to_the_latest_request_places_the_region() -> None:
    asked_twice = RegionTop().asked().moved((1, 2, 10)).asked()

    first = asked_twice.answered(3)

    assert (first.top, first.answered(5).top) == (None, 5)


def test_an_answer_nothing_asked_for_changes_nothing() -> None:
    assert RegionTop(top=4).answered(7) == RegionTop(top=4)


def test_frames_move_a_placed_region() -> None:
    assert RegionTop(top=2).moved((3, 2, 10)) == RegionTop(top=5)


def test_a_resize_loses_the_region_but_not_the_requests() -> None:
    assert RegionTop(top=4, unanswered=((),)).lost() == RegionTop(top=None, unanswered=((),))
