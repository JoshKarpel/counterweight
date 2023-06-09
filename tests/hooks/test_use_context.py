from contextvars import ContextVar

import pytest

from reprisal.hooks import Anchor, provide_context, use_context

ctx = ContextVar("ctx", default="default")


def test_context_is_reset_after_with_block() -> None:
    def _() -> None:
        assert use_context(ctx) == "default"

        with provide_context(ctx, "foo"):
            assert use_context(ctx) == "foo"

        assert use_context(ctx) == "default"

        with provide_context(ctx, "bar"):
            assert use_context(ctx) == "bar"

        assert use_context(ctx) == "default"

    anchor = Anchor(_)
    anchor()


def inner() -> str:
    return use_context(ctx)


def outer(value: str | None) -> str:
    if value is not None:
        with provide_context(ctx, value):
            return inner()
    else:
        return inner()


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, "default"),
        ("foo", "foo"),
    ],
)
def test_context_is_used_in_inner_if_set(value: str | None, expected: str) -> None:
    anchor = Anchor(outer)

    assert anchor(value) == expected
