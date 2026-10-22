"""
The keys that identify the shadow tree's nodes, apart from the hooks they key,
so a value that names a node, such as a `Subtree`, can make a fresh one without importing the hooks.
"""

from __future__ import annotations

from itertools import count
from typing import NewType

# Identifies one mounted node across frames, for as long as its hooks carry over.
NodeKey = NewType("NodeKey", int)

_node_keys = count()


def next_node_key() -> NodeKey:
    """A key no other node in the process has, so keys from different apps and tests never collide."""
    return NodeKey(next(_node_keys))
