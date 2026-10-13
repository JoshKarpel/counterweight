# Components

A component is a function decorated with [`@component`][counterweight.components.component]
that returns an element and holds state through [hooks](../hooks/index.md).
This page covers how a component's state survives from one render to the next,
how to use keys to control that,
and how to skip re-running a component whose arguments didn't change.
The rules are the same as React's;
React's [Preserving and Resetting State](https://react.dev/learn/preserving-and-resetting-state)
covers the same ground with interactive examples.

## How a component keeps its state

A render calls a component function again when that component's state changed,
or when the component that returned it was called again
(unless it's a [`memo`](#skipping-a-component-whose-arguments-didnt-change) component
whose arguments didn't change),
and builds a new tree, keeping the previous render's output for every component it didn't call.
Counterweight then pairs each component in the new tree with one from the previous render.
A component that finds a partner **continues** it:
it keeps its hooks, so `use_state` returns the stored value and its effects keep running.
A component that finds no partner **mounts** with fresh hooks,
and a previous component that nobody paired with **unmounts**:
its effects are cancelled, its state is discarded,
and calling one of its `use_state` setters does nothing.

Pairing happens among siblings (the children of one parent),
and a partner must be the same component function.
Among those:

- An unkeyed component continues the unkeyed sibling at the same index.
- A keyed component continues the sibling that had the same key, wherever that sibling was.

So without keys, a component's position is its identity.
That is the right default for most of a UI,
where the same component sits in the same place every render,
and it is why an ordinary unkeyed component keeps its state across renders.

## When position isn't identity

Position stops being identity when the children come from data that changes shape.
Here each row of a to-do list holds its own checkmark:

```python
from counterweight.components import component
from counterweight.elements import Div, Text
from counterweight.handlers import on_click
from counterweight.hooks import use_state


@component
def todo_row(title: str) -> Text:
    done, set_done = use_state(False)

    return Text(content=f"[{'x' if done else ' '}] {title}", on_input=on_click(lambda: set_done(not done)))


@component
def todo_list(titles: list[str]) -> Div:
    return Div(children=[todo_row(title) for title in titles])
```

Check off `a`, then remove it from `titles`:

```text
before: [x] a    after: [x] b
        [ ] b           [ ] c
        [ ] c
```

Row `b` is now checked.
The component at index 0 continued the old index-0 row, `a`'s state included,
and was only told its title is now `b`.
The old index-2 row is the one that unmounted.
State stays with the position, while the data moved.

Key each row by the item it shows, and the state follows the item instead:

```python
@component
def todo_list(titles: list[str]) -> Div:
    return Div(children=[todo_row(title).with_key(title) for title in titles])
```

```text
before: [x] a    after: [ ] b
        [ ] b           [ ] c
        [ ] c
```

Now `a`'s row is the one that unmounts, and `b` and `c` keep their own state.
The same holds when keyed rows are reordered or a row is inserted at the front:
each existing row keeps its state and effects, and only a new key mounts.

The same shift happens without any list,
when a child conditionally appears in front of a component:

```python
Div(children=[*([Text(content="Saved!")] if saved else []), editor()])
```

When `saved` becomes true, `editor` moves from index 0 to index 1,
finds no unkeyed sibling there, and remounts with empty state.
Either key it (`editor().with_key("editor")`),
or keep its position fixed by always rendering the slot in front of it:

```python
Div(children=[Text(content="Saved!" if saved else ""), editor()])
```

### Choosing a key

- Use whatever identifies the item in your data: a database id, a file path, a title if titles are
  unique.
- Keys are strings, so convert a numeric id with `with_key(str(item.id))`.
- Don't use the item's index in the list.
  `with_key(str(i))` behaves the same as no key at all, because the key follows the position, not the item.
- A key only has to be unique among siblings, so two separate lists can reuse the same keys.
  Keyed siblings that share a key raise `DuplicateKey`; any number of unkeyed siblings is fine.

## Resetting state with a key

Since a different key means a different component,
changing a component's key is how you throw away its state on purpose.
The Wordle example keys its game board by the solution word:

```python
play(solution=solution, stop_playing=stop_playing).with_key(solution)
```

Starting a new game picks a new solution, so a fresh `play` mounts with an empty board,
and `play` doesn't need to reset each of its own state variables.
Adding a key to a component or removing one counts as a change too.

## Keys go on components

Only components take a key; elements like `Div` and `Text` are always paired by position.
A component inside an element moves only as far as that element does,
so to move a subtree along with its state, make the root of that subtree a component and key it.

## Skipping a component whose arguments didn't change

A component that re-runs calls every component it returns again,
even when it passes them the same arguments as last render.
Declare a component `memo` to skip it in that case:

```python
@component(memo=True)
def todo_row(title: str) -> Text: ...
```

When its parent re-runs and passes it arguments equal (`==`) to last render's, with the same key,
a `memo` component keeps its previous output instead of re-running,
along with every component below it.
It still re-runs when its own state changes,
and on the renders that re-run everything: the first one, and those after a resize or a suspend.

`memo` is opt-in, as it is in React, because it isn't free and isn't always right:

- Comparing the arguments costs something on every render, and `==` on a large argument walks all of it.
  A cheap component can cost less to re-run than to compare.
- A function the parent creates while rendering, such as a lambda passed as a handler,
  is a new object every render and never equals the previous one, so the component always re-runs.
- The component's output has to depend only on its arguments and its hooks.
  One that also reads a module-level value, or an argument that is mutated in place,
  keeps showing what it showed when it last ran.
- In a list, an unkeyed `memo` component compares its arguments with whatever item was at its index last render,
  so when the list is reordered, most of them change and re-run.
  [Key](#choosing-a-key) the items to compare each one with itself.

[Performance](../performance.md) walks through finding the components a frame re-runs,
and each way `memo` and `use_memo` can miss or go stale.

### Keeping components pure

A component has to be **pure**: given the same arguments and hook state,
it returns the same element, however many times it's called.
A component that isn't re-run, `memo` or not, keeps showing the output from its last run,
so one that also reads something else, such as a module-level value or the time, goes stale.
To show the time, read it with [`use_clock`](../hooks/use_clock.md).
To show something else that changes on its own, such as a value polled from a server,
keep it in state and update it from [`use_effect`](../hooks/use_effect.md).

Pass `check_purity=True` to `app` in tests to catch an impure component:
after each render, every component is run again with the same arguments and hooks,
and if that builds a different tree,
the app raises `ImpureComponent` naming the first component whose output differs.
Elements are compared with `==`, and where that fails, piece by piece,
with handlers compared by their code and the values they captured,
since a re-run creates new ones that never `==` the old ones.
The second run also raises `InconsistentHookExecution` for a component that calls a different number of hooks,
and checks [`use_memo`](../hooks/use_memo.md) the same way:
each cached value is computed again, and one that differs raises `StaleMemo`.
It costs as much as re-running everything, so leave `check_purity` off outside tests.
[`use_ref`](../hooks/use_ref.md#not-reading-or-writing-a-ref-while-rendering) covers what it catches for refs.

## API

::: counterweight.components.component
::: counterweight.components.Component
