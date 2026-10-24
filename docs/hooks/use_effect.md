# `use_effect`

`use_effect` runs an async function, the effect's `setup`, alongside a component:
it starts after the frame that mounts the component is painted,
and starts again whenever its dependencies change.
Effects are for work that takes time or reaches outside the tree,
such as fetching data, subscribing to something, or running a program,
so that rendering stays [pure](../components/index.md#keeping-components-pure).
An effect usually ends by setting state, which renders what it found.

<!-- example: use_effect_forecast.py:example -->

=== "Fetched"

    ![The forecast for Lisbon, fetched](../assets/use-effect-forecast.svg)

=== "Fetching, after Right"

    ![Oslo selected, with its forecast still being fetched](../assets/use-effect-forecast-fetching.svg)

`forecast` fetches the forecast for its `city` when it mounts,
and again each time `city` changes, since `city` is in its `deps`.
It keeps the city each summary is for, so right after Right selects Oslo,
it shows that Oslo's forecast is on its way, rather than Lisbon's forecast under Oslo's name.

A change of `city` also cancels the fetch already in flight,
so pressing Right twice quickly never shows Oslo's forecast once Lima is selected,
however late Oslo's answer would have arrived.
React's effects need an `ignore` flag set in their cleanup function for that;
here, the cancelled fetch never reaches its `set_fetched`.

## Dependencies

`deps` says when the effect starts again:

- **A tuple of values** starts it again on each render where any of them changed, compared with `==`.
  List every value the effect reads that can change between renders: arguments, state, and anything computed from them.
  An effect that reads a value left out keeps using the value from the render that started it.
- **`()`** starts it once, when the component mounts, and keeps it running until the component unmounts.
- **`None`**, the default, starts it again on every render of the component.

A setter from [`use_state`](use_state.md) and the sender from [`use_controls`](use_controls.md)
are the same on every render, so they can be left out.
An effect that runs for a long time and updates state from its previous value should pass the setter a function,
since the state it closed over doesn't change
(see [An effect that outlives its render](use_state.md#updating-state-from-its-previous-value)).

To do something on a schedule, such as animating or counting down,
read the time with [`use_clock`](use_clock.md) instead of sleeping in a loop in an effect
(see [Why compute from elapsed time?](use_clock.md#why-compute-from-elapsed-time)).

## Cleaning up

Where a React effect returns a cleanup function, a Counterweight effect is cancelled:
it runs as an [`asyncio.Task`][asyncio.Task], which is cancelled when its component unmounts
or its dependencies change (see [Effect Cancellation](#effect-cancellation)).
The cancellation raises [`CancelledError`][asyncio.CancelledError] at whatever `await` the effect is waiting on,
so cleanup goes in a `finally` block:

```python
@component
def service_status(url: str) -> Text:
    status, set_status = use_state("connecting")

    async def watch() -> None:
        connection = await connect(url)
        try:
            while True:
                set_status(await connection.status())
                await asyncio.sleep(5)
        finally:
            await connection.close()

    use_effect(watch, deps=(url,))

    return Text(content=status)
```

The next frame waits for every cancelled effect to finish, so keep cleanup quick,
and don't catch `CancelledError` without raising it again:
an effect that swallows its cancellation and returns fails the app with a `RuntimeError`,
and one that keeps going holds up every frame after it.

## Effect Cancellation

Effects are canceled by the framework when one of the following conditions is met:

- The component that created the effect is unmounted.
- The effect's dependencies change and the effect's `setup` function is going to be re-run.

!!! note "Effect cancellation is synchronous"

    Note that the effect is *synchronously cancelled*
    (i.e., the [`Task`][asyncio.Task] that represents the effect is cancelled and then `await`ed;
    see [this discussion](https://discuss.python.org/t/asyncio-cancel-a-cancellation-utility-as-a-coroutine-this-time-with-feeling/26304/5))
    before the next render cycle starts.
    Assuming that you do not mess with the cancellation yourself from inside the effect setup function,
    the effect will definitely stop running before the next frame is rendered.

    Within a render, every effect that is being cancelled is cancelled concurrently,
    and all of them finish before any effect's `setup` function starts,
    so an effect that holds something exclusive (a subscription, a terminal mode)
    releases it before its own re-run or a sibling's effect can acquire it.

## Testing

An [autopilot](../autopilot.md) hands the app its next step as soon as the last one has rendered,
without waiting for effects.
To check what an effect shows, wait for it with [`WaitFor`][counterweight.autopilot.WaitFor],
as the screenshots above wait for `Sunny` to appear on screen
(see [Waiting for real work](../autopilot.md#waiting-for-real-work)).

## API

::: counterweight.hooks.use_effect
::: counterweight.hooks.Setup
::: counterweight.hooks.Deps
