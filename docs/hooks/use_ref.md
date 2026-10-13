# `use_ref`

`use_ref` keeps a mutable box, a [`Ref`][counterweight.hooks.Ref],
for as long as the component is mounted.
Changing `ref.current` doesn't render anything, which is what sets a ref apart from state:
it holds what the component needs to remember but doesn't show.

## Using a ref outside of rendering

Read and write `current` in handlers and effects, which run after a render, not while rendering.

```python
from counterweight.components import component
from counterweight.elements import Text
from counterweight.events import InputEvent, InputResponse, KeyPressed, Receiver
from counterweight.hooks import use_focus, use_ref, use_state
from counterweight.keys import Key


@component
def line_entry() -> Text:
    use_focus(auto_focus=True)
    typed = use_ref(list[str]())
    line, set_line = use_state("")

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.Enter):
                set_line("".join(typed.current))
                typed.current.clear()
                return ()
            case KeyPressed(key=key):
                typed.current.append(key)
                return ()
            case _:
                return None

    return Text(content=line, on_input=on_input)
```

`line_entry` collects keys without rendering, and renders only when Enter sets `line`.
Rendering reads `line`, never `typed`.

Refs fit:

- **Values a handler builds up** before it sets state, as `typed` does above.
- **Handles to things outside the tree**, such as a task or a client,
  that a handler or an effect uses.
- **Something expensive to build once**, with a function as the initial value:
  `use_ref(lambda: build_index())` calls `build_index` only on the first render.

## Not reading or writing a ref while rendering

A component [has to be pure](../components/index.md#keeping-components-pure):
given the same arguments and hook state, it returns the same element.
A ref changes without a render, so it isn't part of that state,
and a render can skip a component and keep its previous output.

**Writing a ref while rendering** happens once per run,
and which renders run a component depends on what else changed:

```python
@component
def counts_renders() -> Text:
    renders = use_ref(0)
    renders.current += 1
    return Text(content=f"rendered {renders.current} times")
```

The count goes up only on the renders that re-run `counts_renders`, so it says nothing reliable.
Count something you can name instead, such as the events a handler saw, in state.

**Reading a ref while rendering** shows whatever it held when the component last ran:

```python
@component
def shows_change(value: int) -> Text:
    previous = use_ref(value)
    text = f"{previous.current} -> {value}"
    previous.current = value
    return Text(content=text)
```

Once `previous` holds `value`, running `shows_change` again shows `value -> value`.
Keep the previous value in state, and set it together with the current one.

Reading `current` once to start with,
such as passing `use_ref(lambda: build_index()).current` to a child,
is fine as long as nothing changes it afterward.

With `check_purity` on, the second run of every component gets copies of its refs,
so assigning `current` there leaves the component's refs alone,
and a component whose output depends on what a ref held raises `ImpureComponent`.
The copies hold the same objects, so changing the object `current` holds,
such as appending to a list, still reaches the component's ref.

## API

::: counterweight.hooks.use_ref
::: counterweight.hooks.Ref
