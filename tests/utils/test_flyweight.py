from dataclasses import dataclass, replace
from typing import ClassVar

import pytest

from counterweight._utils import flyweight


@flyweight(maxsize=2**8)
@dataclass(frozen=True, slots=True, kw_only=True)
class _KW:
    x: int
    y: int = 0


@flyweight(maxsize=2**8)
@dataclass(frozen=True, slots=True)
class _Pos:
    x: int
    y: int


def test_same_kwargs_returns_same_instance() -> None:
    a = _KW(x=1, y=2)
    b = _KW(x=1, y=2)
    assert a is b


def test_different_kwargs_returns_different_instance() -> None:
    a = _KW(x=1, y=2)
    b = _KW(x=1, y=3)
    assert a is not b


def test_default_kwarg_interned_with_explicit_default() -> None:
    a = _KW(x=5)
    b = _KW(x=5, y=0)
    assert a is b


def test_positional_args_interned() -> None:
    a = _Pos(1, 2)
    b = _Pos(1, 2)
    assert a is b


def test_positional_different_args_not_interned() -> None:
    a = _Pos(1, 2)
    b = _Pos(1, 3)
    assert a is not b


def test_field_values_correct() -> None:
    obj = _KW(x=7, y=9)
    assert obj.x == 7
    assert obj.y == 9


def test_positional_dataclass_field_values_correct() -> None:
    obj = _Pos(3, 4)
    assert obj.x == 3
    assert obj.y == 4


def test_mixed_positional_and_kwargs_interned_with_all_positional() -> None:
    a = _Pos(1, 2)
    b = _Pos(1, y=2)
    assert a is b


def test_mixed_positional_and_kwargs_interned_with_all_kwargs() -> None:
    a = _Pos(x=1, y=2)
    b = _Pos(1, y=2)
    assert a is b


@flyweight(maxsize=2**8)
@dataclass(frozen=True, slots=True)
class _Counted:
    x: int
    post_inits: ClassVar[list[int]] = []

    def __post_init__(self) -> None:
        self.post_inits.append(self.x)


def test_repeated_construction_skips_post_init() -> None:
    _Counted(41)
    _Counted(41)
    assert _Counted.post_inits.count(41) == 1


def test_unknown_kwarg_raises() -> None:
    with pytest.raises(TypeError):
        _KW(x=1, z=2)  # type: ignore[call-arg]


def test_missing_arg_raises() -> None:
    with pytest.raises(TypeError):
        _Pos(1)  # type: ignore[call-arg]


def test_instances_have_the_decorated_class_as_their_type() -> None:
    assert type(_Pos(5, 6)) is _Pos


def test_replace_returns_interned_instance() -> None:
    assert replace(_KW(x=8, y=1), y=2) is _KW(x=8, y=2)


def test_unhashable_dataclass_is_rejected() -> None:
    @dataclass(slots=True)
    class Mutable:
        x: int

    with pytest.raises(TypeError, match="unhashable"):
        flyweight()(Mutable)
