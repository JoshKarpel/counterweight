# Components

A component is a function decorated with [`@component`][counterweight.components.component]
that returns an element and holds state through [hooks](../hooks/index.md).
This page covers how a component's state survives from one render to the next,
and how to use keys to control that.
The rules are the same as React's;
React's [Preserving and Resetting State](https://react.dev/learn/preserving-and-resetting-state)
covers the same ground with interactive examples.

## How a component keeps its state

Every render calls your component functions again and builds a new tree.
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
from counterweight.events import MouseEvent, MouseUp
from counterweight.hooks import use_state


@component
def todo_row(title: str) -> Text:
    done, set_done = use_state(False)

    def on_mouse(event: MouseEvent) -> None:
        match event:
            case MouseUp(button=1):
                set_done(not done)

    return Text(content=f"[{'x' if done else ' '}] {title}", on_mouse=on_mouse)


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

## API

::: counterweight.components.component
::: counterweight.components.Component
