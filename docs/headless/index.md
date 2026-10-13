# Headless Components

A headless component gives a component the behavior of a common control,
such as which keys edit text and where the cursor goes,
and leaves drawing it to the component,
as [Headless UI](https://headlessui.com/)
and [React Aria](https://react-spectrum.adobe.com/react-aria/hooks.html) do for the web.
Each one is a hook in `counterweight.headless`,
and `counterweight.widgets` draws each one way, for when you don't need your own look:

| Hook                                  | Widget        | Edits                     |
|---------------------------------------|---------------|---------------------------|
| [`use_text_input`](use_text_input.md) | `text_input`  | One line of text          |
| [`use_text_area`](use_text_area.md)   | `text_area`   | Text that wraps onto rows |
