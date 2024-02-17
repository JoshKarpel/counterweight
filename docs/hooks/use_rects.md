# `use_rects`

## API

::: counterweight.hooks.use_rects
::: counterweight.hooks.Rects

!!! tip "Use `use_hovered` for detecting hover state"

    `use_rects` is a low-level hook.
    For the common use case of detecting whether the mouse is hovering over an element,
    use the higher-level [`use_hovered`](./use_hovered.md) hook instead.

!!! warning "This is not a stateful hook"

    `use_rects` is not a stateful hook: it does not use `use_state` under the hood.
    That means that if the dimensions of the component's top-level element change
    in a way that is not connected to some other state change
    (e.g., if a sibling component changes size),
    using this hook will not cause the component to re-render.
