# `use_effect`

## API

::: counterweight.hooks.use_effect
::: counterweight.hooks.Setup
::: counterweight.hooks.Deps

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
