from __future__ import annotations


def clamp[C: (int, float)](min_: C, val: C, max_: C) -> C:
    return max(min_, min(val, max_))


__all__ = ["clamp"]
