"""
Whether two values a render produced would behave the same, which `check_purity` uses to catch impure components.

Plain `==` can't answer that for handlers: a re-run builds new closures, which never equal the old ones.
"""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from functools import partial
from types import CellType, FunctionType
from typing import TYPE_CHECKING, TypeIs

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

EMPTY_CELL = object()


def equivalent(a: object, b: object) -> bool:
    """
    Whether `a` and `b` are the same, comparing values with `==`
    and functions by what they would do when called:
    two functions are equivalent when they share a `__code__` object,
    have equivalent defaults, and their closure cells hold equivalent values,
    and two `functools.partial`s when their `func`, `args` and `keywords` are equivalent.
    Tuples, lists, dicts and dataclasses are compared item by item by the same rule,
    so a handler anywhere inside an element is compared as a handler.
    Every other value, other callables included, is compared with `==`.
    """
    return equivalent_within(a, b, set())


def equivalent_within(a: object, b: object, comparing: set[tuple[int, int]]) -> bool:
    """
    `equivalent`, counting a pair of functions already in `comparing` as the same,
    so a closure that refers to itself terminates.
    A pair found different ends the whole comparison, so every pair left in `comparing` is equivalent or pending.
    """
    if a is b:
        return True

    if type(a) is not type(b):
        return a == b

    match a, b:
        case FunctionType(), FunctionType():
            # Only functions are registered: they outlive the comparison,
            # while the tuples `cells` builds are freed and their ids reused.
            pair = (id(a), id(b))
            if pair in comparing:
                return True
            comparing.add(pair)
            return (
                a.__code__ is b.__code__
                and equivalent_within(a.__defaults__, b.__defaults__, comparing)
                and equivalent_within(a.__kwdefaults__, b.__kwdefaults__, comparing)
                and equivalent_within(cells(a.__closure__), cells(b.__closure__), comparing)
            )
        case partial(), partial():
            return (
                equivalent_within(a.func, b.func, comparing)
                and equivalent_within(a.args, b.args, comparing)
                and equivalent_within(a.keywords, b.keywords, comparing)
            )
        case tuple() | list(), tuple() | list():
            return len(a) == len(b) and all(equivalent_within(x, y, comparing) for x, y in zip(a, b))
        case dict(), dict():
            return a.keys() == b.keys() and all(equivalent_within(a[k], b[k], comparing) for k in a)
        case _ if compares_fields(a):
            return all(
                equivalent_within(getattr(a, f.name), getattr(b, f.name), comparing) for f in fields(a) if f.compare
            )
        case _:
            return a == b


def compares_fields(value: object) -> TypeIs[DataclassInstance]:
    """Whether `value` is a dataclass instance whose `==` compares its fields, rather than its identity."""
    return is_dataclass(value) and not isinstance(value, type) and type(value).__dataclass_params__.eq  # type: ignore[attr-defined]


def cells(closure: tuple[CellType, ...] | None) -> tuple[object, ...]:
    """The values a closure's cells hold, with `EMPTY_CELL` for a cell whose variable isn't bound yet."""
    if closure is None:
        return ()

    return tuple(cell_contents(cell) for cell in closure)


def cell_contents(cell: CellType) -> object:
    try:
        return cell.cell_contents
    except ValueError:
        return EMPTY_CELL
