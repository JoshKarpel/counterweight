from __future__ import annotations

from copy import deepcopy


def merge(a: dict[str, object], b: dict[str, object]) -> dict[str, object]:
    a = deepcopy(a)

    for key, b_val in b.items():
        if key in a:
            a_val = a[key]
            if isinstance(b_val, dict) and isinstance(a_val, dict):
                merge(a_val, b_val)
            else:
                a[key] = b_val
        else:
            a[key] = b_val

    return a
