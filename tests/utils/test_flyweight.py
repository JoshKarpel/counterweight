from dataclasses import dataclass, replace
from typing import ClassVar

import pytest

from counterweight._utils import flyweight

# Each test applies `flyweight` itself, rather than these classes being decorated where they're defined,
# so that mutation testing runs the decorator under test instead of the copy that ran at import.


@dataclass(frozen=True, slots=True, kw_only=True)
class KW:
    x: int
    y: int = 0


@dataclass(frozen=True, slots=True)
class Pos:
    x: int
    y: int


def test_same_kwargs_returns_same_instance() -> None:
    interned = flyweight()(KW)

    assert interned(x=1, y=2) is interned(x=1, y=2)


def test_different_kwargs_returns_different_instance() -> None:
    interned = flyweight()(KW)

    assert interned(x=1, y=2) is not interned(x=1, y=3)


def test_default_kwarg_interned_with_explicit_default() -> None:
    interned = flyweight()(KW)

    assert interned(x=5) is interned(x=5, y=0)


def test_positional_args_interned() -> None:
    interned = flyweight()(Pos)

    assert interned(1, 2) is interned(1, 2)


def test_positional_different_args_not_interned() -> None:
    interned = flyweight()(Pos)

    assert interned(1, 2) is not interned(1, 3)


def test_field_values_correct() -> None:
    obj = flyweight()(KW)(x=7, y=9)

    assert (obj.x, obj.y) == (7, 9)


def test_positional_dataclass_field_values_correct() -> None:
    obj = flyweight()(Pos)(3, 4)

    assert (obj.x, obj.y) == (3, 4)


def test_mixed_positional_and_kwargs_interned_with_all_positional() -> None:
    interned = flyweight()(Pos)

    assert interned(1, 2) is interned(1, y=2)


def test_mixed_positional_and_kwargs_interned_with_all_kwargs() -> None:
    interned = flyweight()(Pos)

    assert interned(x=1, y=2) is interned(1, y=2)


@dataclass(frozen=True, slots=True)
class Counted:
    x: int
    post_inits: ClassVar[list[int]] = []

    def __post_init__(self) -> None:
        self.post_inits.append(self.x)


def test_repeated_construction_skips_post_init() -> None:
    Counted.post_inits.clear()
    interned = flyweight()(Counted)

    interned(41)
    interned(41)

    assert Counted.post_inits == [41]


def test_unknown_kwarg_raises() -> None:
    interned = flyweight()(KW)

    with pytest.raises(TypeError):
        interned(x=1, z=2)  # type: ignore[call-arg]


def test_missing_arg_raises() -> None:
    interned = flyweight()(Pos)

    with pytest.raises(TypeError):
        interned(1)  # type: ignore[call-arg]


def test_instances_have_the_decorated_class_as_their_type() -> None:
    interned = flyweight()(Pos)

    assert type(interned(5, 6)) is interned


def test_decorated_class_subclasses_the_original_and_keeps_its_names_and_docstring() -> None:
    @dataclass(frozen=True, slots=True)
    class Nested:
        """A class whose qualified name differs from its name."""

    interned = flyweight()(Nested)

    assert issubclass(interned, Nested)
    assert (interned.__name__, interned.__qualname__, interned.__module__, interned.__doc__) == (
        "Nested",
        "test_decorated_class_subclasses_the_original_and_keeps_its_names_and_docstring.<locals>.Nested",
        __name__,
        "A class whose qualified name differs from its name.",
    )


def test_instances_have_no_instance_dictionary() -> None:
    assert not hasattr(flyweight()(Pos)(1, 2), "__dict__")


def test_replace_returns_interned_instance() -> None:
    interned = flyweight()(KW)

    assert replace(interned(x=8, y=1), y=2) is interned(x=8, y=2)


def test_instances_evicted_beyond_maxsize_are_built_again() -> None:
    interned = flyweight(maxsize=1)(Pos)
    first = interned(1, 2)

    interned(3, 4)

    assert interned(1, 2) is not first


def test_unhashable_dataclass_is_rejected() -> None:
    @dataclass(slots=True)
    class Mutable:
        x: int

    with pytest.raises(TypeError, match="unhashable"):
        flyweight()(Mutable)
