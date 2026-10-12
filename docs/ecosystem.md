# Ecosystem

This page places Counterweight next to the three terminal UI frameworks closest to it:
[Textual](https://textual.textualize.io/), [Ink](https://github.com/vadimdemedes/ink)
and [Ratatui](https://ratatui.rs/).
It covers how each one is programmed, what each one has that Counterweight doesn't,
and when you'd pick each.
It doesn't benchmark them.

## Where Counterweight fits

Counterweight is a Python framework with React's programming model.
Each of the others shares one of those with it:

- **Textual** is also Python, but you build its UIs from widget objects that you query and update.
- **Ink** is also React (it's a renderer for React itself), but you write it in JavaScript or TypeScript.
- **Ratatui** shares neither, but Counterweight draws to the terminal the way Ratatui does,
  by painting every frame into a buffer and writing only the cells that changed.

So the short version is: choose Counterweight over Textual for the programming model,
over Ink to write Python,
and over Ratatui to have the framework own the state, the event loop and the layout.

## At a glance

| | Counterweight | Textual | Ink | Ratatui |
|---|---|---|---|---|
| Language | Python | Python | JavaScript, TypeScript | Rust |
| You write | Functions that return elements, with hooks for state | Widget classes composed into a DOM, with reactive attributes and message handlers | React components | Code that draws widgets into a buffer each frame |
| Styles | `Style` values on each element, merged from utilities | TCSS stylesheets that match widgets by selector | Props on `<Box>` and `<Text>` | `Style` values passed to each widget |
| Layout | CSS flexbox and grid, via [taffy](https://github.com/DioxusLabs/taffy) | Vertical, horizontal, grid and dock layouts of its own | Flexbox, via [Yoga](https://www.yogalayout.dev/) | Constraints solved by [Cassowary](https://github.com/ratatui/kasuari) |
| Event loop | Counterweight's | Textual's | Ink's | Yours |
| Screen | Full screen (inline: [#393](https://github.com/JoshKarpel/counterweight/issues/393)) | Full screen or inline | Inline or full screen | Full screen, inline or a fixed area |
| Mouse | Yes | Yes | No | Through the backend's events |
| Focus | No ([#390](https://github.com/JoshKarpel/counterweight/issues/390)) | Yes | Yes | No |
| Text input | No ([#391](https://github.com/JoshKarpel/counterweight/issues/391)) | Built in | Third-party packages | Third-party crates |
| Scrolling | No ([#388](https://github.com/JoshKarpel/counterweight/issues/388), [#389](https://github.com/JoshKarpel/counterweight/issues/389)) | Built in | Third-party packages | `Paragraph` scrolling and a scrollbar widget |
| Wide characters | No ([#392](https://github.com/JoshKarpel/counterweight/issues/392)) | Yes | Yes | Yes |
| Platforms | Linux, macOS | Linux, macOS, Windows | Not stated | Linux, macOS, Windows |

## Textual

Textual is the closest alternative in the same language, and the most complete:
it has a large [widget library](https://textual.textualize.io/widget_gallery/)
with text inputs, text areas, tables, trees and Markdown viewers,
focus handling, scrolling, an inline mode, Windows support,
and a way to serve apps in a browser.

The difference is how you describe a UI.
In Textual, a UI is a tree of widget objects that live across renders.
You change it by setting reactive attributes, by querying for widgets and calling methods on them,
and by handling messages that bubble up the tree.
What the screen shows at any moment depends on the history of those changes.

In Counterweight, a UI is a function of state.
Components are functions that return elements,
and every change to state renders the tree again from those functions,
so what the screen shows depends only on the current state.
A component's props are its function arguments,
so a type checker checks every place a component is used.

Styling differs in the same direction.
Textual's TCSS stylesheets match widgets by type, ID and class from a separate file or class variable,
with a cascade deciding which rule wins.
Counterweight's styles are values written on the element they style,
so you can see what an element looks like without looking anywhere else.

Layout differs too.
Textual's grid has [its own rules](https://textual.textualize.io/guide/layout/),
and it has no flexbox.
Counterweight's layout is the web's flexbox and grid, so what you know from CSS carries over
(see [Layout](layout/index.md)).

Choose Textual when you need its widgets, Windows, inline mode or the browser,
or a framework that many apps already depend on.

## Ink

Ink is React itself, rendering to the terminal.
Its README lists Claude Code, Gemini CLI and GitHub Copilot CLI among the tools built with it.
If you know Ink, you know most of Counterweight:
components, `use_state`, `use_effect`, `use_ref`, `use_memo`, keys and `memo` all follow React's rules
(see [Components](components/index.md)).
Both render only the components whose state changed and the components they return,
skipping `memo` components whose arguments are unchanged.

The main reason to choose Counterweight over Ink is Python.
A Counterweight app runs in the same process as the Python libraries it presents,
such as a model client, a data pipeline or a test runner, with no separate service between them.

Beyond the language:

- Effects are async functions.
  Where a React effect returns a cleanup function,
  a Counterweight effect is cancelled when its dependencies change or its component unmounts,
  so cleanup goes in a `try`/`finally` block (see [`use_effect`](hooks/use_effect.md)).
- Counterweight lays out with grid as well as flexbox.
- Counterweight has mouse input, through `on_mouse` handlers and the
  [`use_mouse`](hooks/use_mouse.md) and [`use_hovered`](hooks/use_hovered.md) hooks.
  Ink has none.

Ink renders inline by default, below the shell prompt, and its `<Static>` component
writes output that stays in the terminal's scrollback.
Counterweight always takes over the whole screen.
Choose Ink for a command-line tool whose output should stay in the scrollback,
or when your code is already in JavaScript.

## Ratatui

Ratatui is an immediate-mode library: it keeps no tree of your UI between frames.
Each frame, your code draws widgets into a screen-sized buffer,
and Ratatui writes the cells that differ from the previous frame's buffer.
Your code owns the event loop, the input handling and all of the state.

Counterweight owns all three.
It keeps the component tree and its state between renders, reads input,
calls your handlers, and renders again when state changes.
Its output stage works like Ratatui's: every render paints a full buffer,
diffs it against the last one, and writes only the changes.

Their layout models differ.
Ratatui splits an area by constraints on the parent,
while Counterweight uses flexbox and grid, where content can size its container.
[Coming from Ratatui?](layout/choosing-a-layout-model.md#coming-from-ratatui)
shows the equivalents of Ratatui's constraints, and where they behave differently.

Choose Ratatui for a single compiled binary, for full control over when and what you draw,
or when frame time is the constraint: Counterweight renders in Python, and Ratatui in Rust.

## What Counterweight doesn't do

These are the gaps you're most likely to hit, with what to do instead:

- **Text input.** There's no text input element.
  Build one from a `KeyPressed` handler that edits a string in `use_state`.
  Tracked in [#391](https://github.com/JoshKarpel/counterweight/issues/391).
- **Scrolling and clipping.** There are no scroll containers,
  and content that overflows its container isn't clipped:
  it paints over the container's border and whatever lies beyond it.
  Keep an offset in `use_state` and render only the slice of your data that fits.
  Tracked in [#388](https://github.com/JoshKarpel/counterweight/issues/388) (clipping) and [#389](https://github.com/JoshKarpel/counterweight/issues/389) (scroll containers).
- **Focus.** Every element's `on_key` handler receives every key press.
  Keep which item is focused in state, and have the other handlers ignore keys.
  Tracked in [#390](https://github.com/JoshKarpel/counterweight/issues/390).
- **Wide characters.** Counterweight counts every character as one cell,
  so CJK characters and most emoji, which terminals draw two cells wide, push the rest of their line out of alignment.
  Tracked in [#392](https://github.com/JoshKarpel/counterweight/issues/392).
- **Inline rendering.** Counterweight always uses the terminal's alternate screen,
  so nothing it draws remains in the scrollback when the app exits.
  Tracked in [#393](https://github.com/JoshKarpel/counterweight/issues/393).
- **Windows.** Counterweight reads input through POSIX terminal APIs,
  and is tested on Linux and macOS.
- **A widget library.** Counterweight provides elements, layout and styles, and you build the widgets.
