# `use_state`

`use_state` gives a component a value that persists across renders, and a setter that changes it.
Setting a different value re-renders the component.

<!-- example: use_state_counter.py:counter -->

![A counter showing a count of 3](../assets/use-state-counter.svg)

Each key press sets the count, which renders `counter` again with the new value:

<!-- cast: use-state-counter -->

`+` and `-` pass the setter a function, since the new count depends on the old one
(see [below](#updating-state-from-its-previous-value)),
and `0` passes it a value, since the reset doesn't.

## Updating state from its previous value

!!! danger "When the new state depends on the old, pass the setter a function"

    `count` is the value as of the render that built the handler,
    and nothing updates it until the next render.
    A setter given a value replaces the state with it,
    so every update computed from `count` before the next render starts from the same stale `count`,
    and only the last one survives. No error is raised: the other updates just vanish.

    Given a function, the setter calls it right away with the latest state, updates included,
    and stores what it returns:

    <!-- fmt: off -->

    ```python
    set_count(count + 1)            # wrong: loses updates made since this render
    set_count(lambda c: c + 1)      # right: builds on the latest state
    ```

    <!-- fmt: on -->

Several updates can land before the next render in ways that are easy to miss,
because each looks like one update when you read the code.

**Two updates in one handler.**
Each `by_value + 1` is computed from the same `by_value`,
while each function builds on what the one before it returned:

<!-- example: use_state_counter.py:twice -->

![After three presses of +, by value shows 3 and by function shows 6](../assets/use-state-plus-two.svg)

After three presses of `+`, `by_value` has gone up by one a press, and `by_function` by two.

**Key presses that arrive together.**
Counterweight routes every event it has read before rendering again,
and a terminal delivers keys together whenever they come faster than one per frame:
fast typing, a held key repeating,
or text pasted into a terminal without [bracketed paste](../input-handling/events.md#handling-pastes).
Each key press's handler sees the same `text`:

```python
text, set_text = use_state("")


def on_input(event: InputEvent, _: Receiver) -> InputResponse:
    match event:
        case KeyPressed(key=key) if len(key) == 1:
            set_text(text + key)  # "abc" typed in one burst leaves text as "c"
            return ()
        case _:
            return None
```

This one hides from tests:
an `autopilot` renders after each event it sends, so every key press there sees the latest `text`,
and so does slow typing by hand.
Write `set_text(lambda t: t + key)`.
For a text field, [`use_text_input`](../headless/use_text_input.md) does this for you,
along with the cursor, the editing keys and pastes.

**An effect that outlives its render.**
An effect closes over the values from the render that started it,
and one with `deps=()` keeps them for as long as the component is mounted:

```python
count, set_count = use_state(0)


async def tick() -> None:
    while True:
        await asyncio.sleep(1)
        set_count(count + 1)  # count stays at 1, since this count is always 0


use_effect(tick, deps=())
```

Pass a value only when the new state doesn't depend on the old,
as in `set_query("")` to clear a field or `set_selected(item.id)` to select an item.
Toggling a flag depends on it, so it takes a function too:
[`toggle`][counterweight.hooks.toggle], as in `set_open(toggle)`.

The setter is the same object on every render,
so a handler that updates state only through functions captures nothing that goes stale,
and can be built once with [`use_memo`](use_memo.md) or passed to a `memo` component.

## Deciding from the latest state

A function passed to the setter moves the state along,
but a handler often has to decide something from the state as well:
whether to claim a key or let it bubble, which controls to return, or which option to hand its parent.
Those decisions are made when the handler returns, before the next render,
so they can't be left to a render or an effect.

The setter returns the state as it settled, the value it was given or what the function returned,
and [`get_state`][counterweight.hooks.get_state] reads the latest state without changing it.
A handler that decides from the state reads it once, at the top,
since nothing else changes it between that read and the handler's own writes:

```python
board, set_board = use_state(Board())


def on_input(event: InputEvent, _: Receiver) -> InputResponse:
    match event:
        case KeyPressed(key=Key.Enter):
            before = get_state(set_board)
            return Bell() if set_board(Board.guessed) == before else ()
        case _:
            return None
```

Enter rings the bell when the board refuses the guess, which the handler learns from what the setter settled at,
even when the keys before it arrived in the same batch and no render has shown their board yet.

Since the setter returns the state, a handler written as a `lambda` whose body is a setter call
returns that state as its response, which isn't one a handler can return.
Write the handler as a function that says whether it claims the event: `()` claims it, and `None` lets it bubble.

## API

::: counterweight.hooks.use_state
::: counterweight.hooks.get_state
::: counterweight.hooks.toggle
::: counterweight.hooks.Getter
::: counterweight.hooks.Setter
::: counterweight.hooks.Editor
