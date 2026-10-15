# Ecosystem

This page places Counterweight next to the four terminal UI frameworks closest to it:
[Textual](https://textual.textualize.io/), [Ink](https://github.com/vadimdemedes/ink),
[Bubble Tea](https://github.com/charmbracelet/bubbletea) and [Ratatui](https://ratatui.rs/).
It covers how each one is programmed, what each one has that Counterweight doesn't,
and when you'd pick each.
It doesn't benchmark them.

## Where Counterweight fits

Counterweight is a Python framework with React's programming model.
Each of the others shares one of those with it:

- **Textual** is also Python, but you build its UIs from widget objects that you query and update.
- **Ink** is also React (it's a renderer for React itself), but you write it in JavaScript or TypeScript.
- **Bubble Tea** shares neither, but its view is also a function of state,
  following the [Elm Architecture](https://guide.elm-lang.org/architecture/) rather than React.
- **Ratatui** shares neither, but Counterweight draws to the terminal the way Ratatui does,
  by painting every frame into a buffer and writing only the cells that changed.

So the short version is: choose Counterweight over Textual for the programming model,
over Ink to write Python,
over Bubble Tea to keep each component's state with the component,
and over Ratatui to have the framework own the state, the event loop and the layout.

## At a glance

| | Counterweight | Textual | Ink | Bubble Tea | Ratatui |
|---|---|---|---|---|---|
| Language | Python | Python | JavaScript, TypeScript | Go | Rust |
| You write | Functions that return elements, with hooks for state | Widget classes composed into a DOM, with reactive attributes and message handlers | React components | A model with `Update` and `View` methods | Code that draws widgets into a buffer each frame |
| Styles | `Style` values on each element, merged from utilities | TCSS stylesheets that match widgets by selector | Props on `<Box>` and `<Text>` | [Lip Gloss](https://github.com/charmbracelet/lipgloss) styles that render strings | `Style` values passed to each widget |
| Layout | CSS flexbox and grid, via [taffy](https://github.com/DioxusLabs/taffy) | Vertical, horizontal, grid and dock layouts of its own | Flexbox, via [Yoga](https://www.yogalayout.dev/) | Joining and placing rendered strings, with Lip Gloss | Constraints solved by [Cassowary](https://github.com/ratatui/kasuari) |
| Event loop | Counterweight's | Textual's | Ink's | Bubble Tea's | Yours |
| Screen | Full screen (inline: [#393](https://github.com/JoshKarpel/counterweight/issues/393)) | Full screen or inline | Inline or full screen | Inline or full screen | Full screen, inline or a fixed area |
| Mouse | Yes | Yes | No | Messages with cell coordinates | Through the backend's events |
| Focus | Yes | Yes | Yes | Tracked in your model | No |
| Text input | One line or wrapped rows, as [headless components](headless/index.md) and the bordered `text_input` and `text_area` widgets built on them | Built in | Third-party packages | [Bubbles](https://github.com/charmbracelet/bubbles)' `textinput` and `textarea` | Third-party crates |
| Scrolling | [Scroll containers](layout/scrolling.md), without a visible scrollbar ([#417](https://github.com/JoshKarpel/counterweight/issues/417)) | Built in | Third-party packages | Bubbles' `viewport` | `Paragraph` scrolling and a scrollbar widget |
| Markdown and syntax highlighting | [Built in](rich-text/markdown.md) | Built in | Third-party packages | [Glamour](https://github.com/charmbracelet/glamour), a separate Charm library | Third-party crates |
| Wide characters | [Yes](elements/text.md#wide-characters) | Yes | Yes | Yes | Yes |
| Platforms | Linux, macOS | Linux, macOS, Windows | Not stated | Linux, macOS, Windows | Linux, macOS, Windows |

## Textual

Textual is the closest alternative in the same language, and the most complete:
it has a large [widget library](https://textual.textualize.io/widget_gallery/)
with data tables, trees, tabs, select menus, checkboxes and progress bars,
text selection, visible scrollbars, an inline mode, Windows support,
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

Choose Textual when you need its widgets, Windows, inline mode or the browser.

## Ink

Ink is React itself, rendering to the terminal.
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
- Counterweight has mouse input, through `on_input` handlers and the
  [`use_mouse`](hooks/use_mouse.md) and [`use_hovered`](hooks/use_hovered.md) hooks.
  Ink has none.

Ink renders inline by default, below the shell prompt, and its `<Static>` component
writes output that stays in the terminal's scrollback.
Counterweight always takes over the whole screen.
Choose Ink for a command-line tool whose output should stay in the scrollback,
or when your code is already in JavaScript.

## Bubble Tea

Bubble Tea is a Go framework built on the Elm Architecture,
with a library of components in [Bubbles](https://github.com/charmbracelet/bubbles)
and styling and layout in [Lip Gloss](https://github.com/charmbracelet/lipgloss).

Like Counterweight, Bubble Tea describes the screen as a function of state.
The difference is where that state lives.
A Bubble Tea app's state is one model value.
Every key press, mouse event, tick and result of a command arrives as a message at the model's `Update` method,
which returns the next model and any commands to run,
and its `View` method turns the model into the text to draw.
A component from Bubbles is a model too,
so a parent holds each child's model as a field,
passes it the messages it should see, stores the model it returns,
and calls its `View` where the child should appear.
Which component has focus is a field the parent keeps,
and choosing where a key press goes is code the parent writes.

In Counterweight, each component keeps its own state in hooks,
and the framework routes input to it:
key presses go to the focused component and bubble up the tree,
and mouse events go to the element under the pointer
(see [Input handling](input-handling/index.md)).
Using a component is calling a function, with no messages to forward or child state to store.

Their layout models differ too.
A Bubble Tea view is a string,
and Lip Gloss lays it out by joining rendered blocks side by side or one above the other,
and by placing a block inside an area of a given size.
Counterweight lays out elements with flexbox and grid before any text is drawn,
so a container can share its space among its children or grow to fit them.

Choose Bubble Tea to write Go, for a single compiled binary, for Windows or inline rendering,
or for the Charm libraries that work with it,
such as prompts and forms ([Huh](https://github.com/charmbracelet/huh))
and serving apps over SSH ([Wish](https://github.com/charmbracelet/wish)).

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

- **Text selection, and scrolling a long line.** [`use_text_input`](headless/use_text_input.md)
  and [`use_text_area`](headless/use_text_area.md) have no selection,
  and a single-line value wider than its box doesn't scroll to keep the cursor in view.
  Tracked in [#420](https://github.com/JoshKarpel/counterweight/issues/420) (scrolling a long line).
- **Inline rendering.** Counterweight always uses the terminal's alternate screen,
  so nothing it draws remains in the scrollback when the app exits.
  Tracked in [#393](https://github.com/JoshKarpel/counterweight/issues/393).
- **Fewer colors.** Counterweight always writes 24-bit color, and ignores `NO_COLOR`,
  so a terminal limited to 256 or 16 colors shows the wrong ones.
  Use a terminal with 24-bit color, and in tmux turn it on with the `RGB` terminal feature.
- **Windows.** Counterweight reads input through POSIX terminal APIs,
  and is tested on Linux and macOS.
- **A widget library.** Counterweight's widgets are a text input and a text area,
  and its [rich text](rich-text/markdown.md) renders Markdown and highlighted code.
  Tables, trees, menus, tabs and the rest you build from elements, layout, styles and hooks.
