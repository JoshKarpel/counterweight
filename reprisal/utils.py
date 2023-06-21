from typing import TypeVar

K = TypeVar("K")
V = TypeVar("V")


def diff(a: dict[K, V], b: dict[K, V]) -> dict[K, V]:
    d = {}
    for key in a.keys() | b.keys():
        a_val = a.get(key)
        if a_val != b.get(key) and a_val is not None:
            d[key] = a_val

    return d
