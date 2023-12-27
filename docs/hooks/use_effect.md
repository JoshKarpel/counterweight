# `use_effect`

## API

::: counterweight.hooks.Setup
::: counterweight.hooks.Deps
::: counterweight.hooks.use_effect

## Effect Cancellation

Effects are cancelled by the framework when one of the following conditions is met:

- The component that created the effect is unmounted.
- The effect's dependencies change and the effect's `setup` function is going to be re-run.
