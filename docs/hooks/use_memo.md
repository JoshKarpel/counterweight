# `use_memo`

`use_memo` keeps a value from one render to the next, computing it again only when its dependencies change.
Use it for:

- **An expensive value derived from arguments or state**, such as a sorted or filtered list.
- **An unchanging part of a component's output.** A component that returns the same element object
  as last render keeps the components inside it from re-running.
- **A handler passed to a [`memo`](../components/index.md#skipping-a-component-whose-arguments-didnt-change)
  component.** A handler defined inline is a new object every render,
  so the `memo` component's arguments never equal last render's.

```python
from counterweight.components import component
from counterweight.elements import Div, Text
from counterweight.hooks import use_memo, use_state


@component
def file_list(paths: tuple[str, ...]) -> Div:
    descending, set_descending = use_state(False)

    ordered = use_memo(lambda: sorted(paths, reverse=descending), deps=(paths, descending))

    return Div(children=[Text(content=path) for path in ordered])
```

`file_list` sorts `paths` again only when `paths` or `descending` changes,
not on every render its parent causes.

A handler to keep stable is `use_memo(lambda: handler, deps)`.

## Dependencies

`deps` has to list every value `compute` reads that can change between renders:
arguments, state, and anything computed from them.
A value left out keeps the cached result from updating when it changes.
For a cached handler, that means the handler keeps acting on the value it captured when it was cached.
When a handler only needs the latest state to compute the next state,
pass a function to the setter (`set_count(lambda count: count + 1)`), which needs no dependency on `count`.

Since hooks are found by their position, `use_memo` can't be called once per item in a loop
whose length can change.
To cache something per item, render a component per item and call `use_memo` in it,
or declare that component `memo`.

Passing `check_purity=True` to `app` in tests catches a missing dependency:
each `use_memo` whose `deps` didn't change also calls `compute`,
and raises `StaleMemo` if the result differs from the cached value.
Handlers are compared by their code and the values they captured, as in
[Keeping components pure](../components/index.md#keeping-components-pure).

## `use_memo` or `functools.lru_cache`?

Both cache a computed value, but they differ in who owns it.
A `use_memo` value belongs to one mounted component.
An [`lru_cache`][functools.lru_cache] value belongs to a function,
and every caller in the process shares it.
So cache a pure function of its arguments with `lru_cache`,
and use `use_memo` for a value that belongs to the component.

| | `use_memo` | `lru_cache` |
|---|---|---|
| Shared by | One component instance | Every caller, across instances, renders and apps |
| Keeps | One value, for the latest `deps` | Up to `maxsize` values, keyed by arguments |
| Freed | When the component unmounts | When evicted, or never with `maxsize=None` |
| Hits when | `deps` equal last render's (`==`) | The arguments equal a cached call's (hash, then `==`) |
| Goes stale when | `compute` reads a value missing from `deps` | The function reads something besides its arguments |
| Defined | Inside the component | At module level |

Prefer `lru_cache` when:

- **The computation reads only its arguments.**
  Its key is its dependency list, so that list can't be incomplete.
- **Many components compute the same thing**, such as rows formatting the same column widths.
  They all share one cache.
- **The inputs alternate**, such as a sort order toggled back and forth.
  `lru_cache` keeps both results, while `use_memo` keeps one and recomputes on every toggle.

The example above, rewritten that way:

```python
from functools import lru_cache


@lru_cache(maxsize=64)
def sorted_paths(paths: tuple[str, ...], descending: bool) -> list[str]:
    return sorted(paths, reverse=descending)


@component
def file_list(paths: tuple[str, ...]) -> Div:
    descending, set_descending = use_state(False)

    return Div(children=[Text(content=path) for path in sorted_paths(paths, descending)])
```

Prefer `use_memo` when:

- **The value captures the component's state or setters**, as a handler does.
- **The inputs can't be hashed**, such as lists, dicts and most mutable objects.
- **The value should go away with the component.**
  A module-level cache keeps every argument and result it holds alive until they're evicted,
  and carries them between tests and between apps run in the same process.
- **The value is part of the component's output**, such as an element whose children shouldn't re-run.
  That's meant for one instance, not for every instance that happens to pass equal arguments.

Don't put `lru_cache` on a function defined inside a component:
every render defines a new function with an empty cache, so it never hits.

## API

::: counterweight.hooks.use_memo
