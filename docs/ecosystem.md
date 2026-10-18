# Ecosystem

This page places Counterweight next to the terminal UI frameworks closest to it:
[Textual](https://textual.textualize.io/), [Ink](https://github.com/vadimdemedes/ink),
[OpenTUI](https://opentui.com/), [Bubble Tea](https://github.com/charmbracelet/bubbletea)
and [Ratatui](https://ratatui.rs/), with shorter notes on [iocraft](#iocraft) and [a few others](#others).
It covers how each one is programmed, what each one has that Counterweight doesn't and the reverse,
when you'd pick each, and what Counterweight doesn't do yet.
It compares Textual 8, Ink 8, OpenTUI 0.6, Bubble Tea 2 and Ratatui 0.30,
and doesn't benchmark them.

## Where Counterweight fits

Counterweight is a Python framework with React's programming model and the web's layout.
We know of no other Python framework built that way.
Each of the others shares part of that with it:

- **Textual** is also Python, but you build its UIs from widget objects that you query and update.
- **Ink** is also React (it's a renderer for React itself), but you write it in JavaScript or TypeScript.
- **OpenTUI** is also React (or Solid) over flexbox, but you write it in TypeScript.
- **Bubble Tea** shares neither, but its view is also a function of state,
  following the [Elm Architecture](https://guide.elm-lang.org/architecture/) rather than React.
- **Ratatui** shares neither, but Counterweight draws to the terminal the way Ratatui does,
  by painting every frame into a buffer and writing only the cells that changed.

So the short version is: choose Counterweight over Textual for the programming model,
over Ink or OpenTUI to write Python,
over Bubble Tea to keep each component's state with the component,
and over Ratatui to have the framework own the state, the event loop and the layout.
Choose one of the others when you need something Counterweight [doesn't do yet](#what-counterweight-doesnt-do-yet).

## At a glance

### How you write an app

| | Counterweight | Textual | Ink | OpenTUI | Bubble Tea | Ratatui |
|---|---|---|---|---|---|---|
| Language | Python | Python | JavaScript, TypeScript | TypeScript, on Bun or Node | Go | Rust |
| You write | Functions that return elements, with hooks for state | Widget classes composed into a DOM, with reactive attributes and message handlers | React components | React or Solid components, or renderable objects | A model with `Update` and `View` methods | Code that draws widgets into a buffer each frame |
| Styles | `Style` values on each element, merged from utilities | TCSS stylesheets that match widgets by selector | Props on `<Box>` and `<Text>` | Props on each element | [Lip Gloss](https://github.com/charmbracelet/lipgloss) styles that render strings | `Style` values passed to each widget |
| Layout | CSS flexbox and grid, via [taffy](https://github.com/DioxusLabs/taffy) | Vertical, horizontal, grid and dock layouts of its own | Flexbox, via [Yoga](https://www.yogalayout.dev/) | Flexbox, via Yoga | Joining, placing and layering rendered strings, with Lip Gloss | Constraints solved by [Cassowary](https://github.com/ratatui/kasuari) |
| Event loop | Counterweight's | Textual's | Ink's | OpenTUI's | Bubble Tea's | Yours |
| Screen | Full screen (inline: [#393](https://github.com/JoshKarpel/counterweight/issues/393)) | Full screen, or inline except on Windows | Inline or full screen | Full screen, or a region at the bottom of the main screen | Inline or full screen | Full screen, inline or a fixed area |
| Platforms | Linux, macOS | Linux, macOS, Windows | Not stated | Linux, macOS, Windows | Linux, macOS, Windows | Linux, macOS, Windows |

### What's built in

| | Counterweight | Textual | Ink | OpenTUI | Bubble Tea | Ratatui |
|---|---|---|---|---|---|---|
| Mouse | Routed to the element under the pointer, with [hover](hooks/use_hovered.md) and [drag](cookbook/draggable-components.md) | Routed to widgets, with hover | None | Routed to the element under the pointer, with hover and drag | Messages with cell coordinates | Through the backend's events |
| Focus | Keys go to the focused component; [Tab order](hooks/use_focus.md), which a dialog can keep within itself | Built in | `useFocus` and `useFocusManager` | Built in, without Tab order | Tracked in your model | None |
| Keys like Shift+Enter (the kitty keyboard protocol) | No ([#419](https://github.com/JoshKarpel/counterweight/issues/419)) | On by default | Opt-in | Supported | On by default | Opt-in, through crossterm |
| Text input | One line or wrapped rows, as [headless components](headless/index.md) and the `text_input` and `text_area` widgets | Built in | Third-party packages | Built in | [Bubbles](https://github.com/charmbracelet/bubbles)' `textinput` and `textarea` | Third-party crates |
| Scrolling | [Scroll containers](layout/scrolling.md), without a visible scrollbar ([#417](https://github.com/JoshKarpel/counterweight/issues/417)) | Built in, with scrollbars | Scroll offsets on `<Box>` | `ScrollBox`, with scrollbars | Bubbles' `viewport` | `Paragraph` scrolling and a `Scrollbar` widget |
| Overlapping boxes | [Relative and absolute positioning](layout/layering.md), with `z` | Layers, offsets and absolute positioning | Absolute positioning; later siblings draw on top | Absolute positioning, with `zIndex` | Lip Gloss layers, with x, y and z | Draw order, with `Clear` |
| Markdown and syntax highlighting | [Built in](rich-text/markdown.md) | Built in | Third-party packages | Built in | [Glamour](https://github.com/charmbracelet/glamour), a separate Charm library | Third-party crates |
| Images | [Pixels](elements/canvas.md) drawn as half blocks ([#441](https://github.com/JoshKarpel/counterweight/issues/441)) | Third-party packages | Third-party packages | kitty graphics, Sixel or blocks | No component | A `Canvas` widget, and images with `ratatui-image` |
| Hyperlinks | [Built in](rich-text/hyperlinks.md) | Built in | Third-party packages | Built in | Lip Gloss's `Hyperlink` | A workaround in an example |
| Embedded terminals | [Built in](terminals/embedding.md), from the pseudo-terminal to the emulator | Third-party, unmaintained | None | An emulator's screen, which you feed a program's output | Small third-party packages | Third-party crates |
| Text selection | The terminal's own, with a modifier held ([#399](https://github.com/JoshKarpel/counterweight/issues/399)) | Built in, with copy | None | Built in, with copy over OSC 52 left to the app | Copy over OSC 52, no selection | None |
| Terminals with fewer colors | Always 24-bit, and ignores `NO_COLOR` ([#440](https://github.com/JoshKarpel/counterweight/issues/440)) | Downgrades, and turns gray for `NO_COLOR` | Downgrades, and ignores `NO_COLOR` | Downgrades to 256 colors, and ignores `NO_COLOR` | Downgrades, and drops colors for `NO_COLOR` | Doesn't downgrade; crossterm drops colors for `NO_COLOR` |
| Testing | [Headless autopilot](autopilot.md), frozen clocks, SVG and text screenshots, and asciicast recordings | `run_test` and `Pilot`, and SVG snapshots | `ink-testing-library` | A test renderer with mock input and frame capture | `teatest`, experimental, and VHS for demos | `TestBackend` and snapshots |

## What Counterweight brings

Beyond Python and React's model, these set Counterweight apart from most of the others:

- **Both flexbox and grid.**
  Textual has grid without flexbox, Ink and OpenTUI have flexbox without grid,
  and Bubble Tea and Ratatui have neither.
  Counterweight lays out with both, as CSS does, so what you know from the web carries over
  (see [Layout](layout/index.md)).
- **Focus order.**
  With the `tab_focus` handler on the root, Tab and Shift+Tab move focus through the focusable components
  in tree order, and the same handler on a dialog keeps Tab inside it while it's open
  (see [`use_focus`](hooks/use_focus.md#moving-focus-within-part-of-the-tree)).
  OpenTUI routes keys to a focused element but leaves moving focus to your code,
  and Bubble Tea and Ratatui leave all of it to your code.
- **Behavior apart from drawing.**
  [Headless components](headless/index.md) such as `use_text_input` give a component a common control's keys
  and state and leave how it looks to you, as React Aria does on the web.
  The bordered widgets are built on them the way an app builds its own,
  so a control that looks different never means reimplementing its keys.
- **Other programs, inside and outside the app.**
  [Embedded terminals](terminals/embedding.md) run a shell, an editor or `htop` in a box,
  with a pseudo-terminal, a real terminal emulator (libghostty) and input encoding built in:
  enough to build a [terminal multiplexer](https://github.com/JoshKarpel/counterweight/blob/main/examples/multiplexer.py).
  [One-shot commands](terminals/commands.md) show a command's output as it runs,
  and an app can [hand its terminal to a program](terminals/programs.md), such as the user's editor, and take it back.
- **Apps that run the same way every time.**
  An [autopilot](autopilot.md) drives an app headlessly, a frozen clock makes time-driven components repeatable,
  and the app writes screenshots and asciicast recordings itself:
  every screenshot and recording in these docs comes from an example run that way.

## Textual

Textual is the closest alternative in the same language, and the most complete:
it has a large [widget library](https://textual.textualize.io/widget_gallery/)
with data tables, trees, tabs, select menus, checkboxes and progress bars,
text selection with copy, visible scrollbars, an inline mode, the kitty keyboard protocol,
colors that adapt to the terminal, Windows support, and a way to serve apps in a browser.
It draws with [Rich](https://github.com/Textualize/rich), the same team's library for formatted terminal output.

The difference is how you describe a UI.
In Textual, a UI is a tree of widget objects that live across renders.
You change it by setting reactive attributes, by querying for widgets and calling methods on them,
and by handling messages that bubble up the tree.
What the screen shows at any moment depends on the history of those changes.
A reactive attribute declared with `recompose=True` rebuilds a widget's children from its `compose` method,
but it replaces them rather than reconciling them, so they lose their state.

In Counterweight, a UI is a function of state.
Components are functions that return elements,
and every change to state renders the tree again from those functions,
reconciling the result with the last render so that each component keeps its state,
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

Choose Textual when you need its widgets, text selection, Windows, inline mode or the browser.

## Ink

Ink is React itself, rendering to the terminal.
If you know Ink, you know most of Counterweight:
components, `use_state`, `use_effect`, `use_ref`, `use_memo`, keys and `memo` all follow React's rules
(see [Components](components/index.md)).
Both render only the components whose state changed and the components they return,
skipping `memo` components whose arguments are unchanged.
What Counterweight doesn't have from React yet is context
([#118](https://github.com/JoshKarpel/counterweight/issues/118))
and `use_reducer` ([#117](https://github.com/JoshKarpel/counterweight/issues/117)).

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
- Counterweight has scroll containers, text inputs, Markdown and syntax highlighting built in,
  where Ink leaves them to other packages.

Ink renders inline by default, below the shell prompt, and its `<Static>` component
writes output that stays in the terminal's scrollback.
Counterweight always takes over the whole screen.
Choose Ink for a command-line tool whose output should stay in the scrollback,
or when your code is already in JavaScript.

## OpenTUI

OpenTUI is a TypeScript framework whose layout, painting and diffing run in a native core written in Zig.
You write it with React, with Solid, or with its renderable objects directly;
[opencode](https://github.com/anomalyco/opencode)'s terminal UI is built on its Solid renderer.
Like Ink, it lays out with Yoga's flexbox, and its React renderer is React itself.

It has more built in than Ink or Counterweight:
inputs, selects and tabs, a scroll box with scrollbars, Markdown and code highlighted with Tree-sitter,
images over the kitty and Sixel graphics protocols, text selection, the kitty keyboard protocol,
Windows support, and a split-footer mode that renders at the bottom of the main screen
and leaves output above it in the scrollback.
Its embedded terminal is an emulator's screen, from the same libghostty that Counterweight's uses,
which your code feeds a program's output and sends its input.

Counterweight differs in its language, in laying out with grid as well as flexbox,
in moving focus with Tab, and in running an embedded terminal's program itself.
Both are young: OpenTUI's releases are pre-1.0 and still change its API, as Counterweight's do.

Choose OpenTUI to write TypeScript, for its widgets and images, for Windows,
or for output that stays in the scrollback.

## Bubble Tea

Bubble Tea is a Go framework built on the Elm Architecture,
with a library of components in [Bubbles](https://github.com/charmbracelet/bubbles)
and styling and layout in [Lip Gloss](https://github.com/charmbracelet/lipgloss).

Like Counterweight, Bubble Tea describes the screen as a function of state.
The difference is where that state lives.
A Bubble Tea app's state is one model value.
Every key press, mouse event, tick and result of a command arrives as a message at the model's `Update` method,
which returns the next model and any commands to run,
and its `View` method turns the model into what to draw:
a string of styled text, with terminal modes such as the alternate screen and mouse tracking.
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
A Bubble Tea view's content is a string,
and Lip Gloss lays it out by joining rendered blocks side by side or one above the other,
by placing a block inside an area of a given size,
and by compositing blocks as layers at given positions.
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

## iocraft

[iocraft](https://github.com/ccbrown/iocraft) is a Rust library with React's model:
component functions, an `element!` macro in place of JSX, keys,
and hooks including `use_state`, `use_effect` and `use_context`,
laid out with taffy's flexbox, as Counterweight's layout is (though without grid).
It's built mainly for a command-line tool's output, which it prints or renders below the prompt,
with full screen as an option.
Choose it for that kind of tool in Rust.

## Others

In Python, [prompt_toolkit](https://github.com/prompt-toolkit/python-prompt-toolkit),
which IPython's prompt is built on, is the usual choice for prompts, REPLs and other input below the shell prompt,
and [urwid](https://urwid.org/) is a long-standing widget toolkit, used by mitmproxy's console.
[Rich](https://github.com/Textualize/rich) formats terminal output and can refresh a region of it,
but doesn't read input.

## What Counterweight doesn't do yet

Counterweight aims to give apps the pieces to build their own controls,
so that a missing widget never has to wait on a release.
Some of what it lacks is that kind of gap, which you can fill today;
the rest needs Counterweight itself to change.

### What you build from the pieces

Counterweight's widgets are a text input, a text area,
a [scroll area](headless/use_scroll_area.md#a-styled-scroll-area),
an [embedded terminal](terminals/embedding.md#a-terminal-widget)
and a command's [output](terminals/commands.md#running-a-command),
and its [rich text](rich-text/markdown.md) renders Markdown and highlighted code.
Tables, trees, menus, tabs, checkboxes, progress bars and dialogs you build from elements, layout, styles and hooks,
as these do:

- A table that sorts by the column you click:
  the [table](https://github.com/JoshKarpel/counterweight/blob/main/examples/table.py) example.
- A menu that opens over the content below a text input: [Autocomplete](cookbook/autocomplete.md).
- A dialog that keeps focus within itself while it's open:
  [`use_focus`](hooks/use_focus.md#moving-focus-within-part-of-the-tree).
- Progress through a series of steps, each with a spinner: [Spinners](cookbook/spinners.md).
- A list of a hundred thousand rows that renders only the rows in view:
  [Reading the scroll](layout/scrolling.md#reading-the-scroll).
- Key sequences such as tmux's prefix key: [Prefix keys](cookbook/prefix-keys.md).

Two smaller gaps are the same kind:

- **A visible scrollbar.** [`use_scroll`](hooks/use_scroll.md) reports how far a container is scrolled,
  how far it can be, and how much of it is in view,
  which is what an absolutely positioned column needs to draw one.
  A built-in one is tracked in [#417](https://github.com/JoshKarpel/counterweight/issues/417).
- **`use_reducer`.** A reducer is a few lines over `use_state`, whose setter takes a function of the current state.
  Tracked in [#117](https://github.com/JoshKarpel/counterweight/issues/117).

### What needs Counterweight to change

These you can't build in an app, with what to do instead:

- **Inline rendering.** Counterweight always uses the terminal's alternate screen,
  so nothing it draws remains in the scrollback when the app exits.
  Tracked in [#393](https://github.com/JoshKarpel/counterweight/issues/393).
- **Text selection.** Counterweight turns on mouse tracking, so selecting text with the terminal
  needs a modifier held (Shift in most terminals),
  and selects a rectangle of cells, borders and neighboring panes included.
  [#399](https://github.com/JoshKarpel/counterweight/issues/399) tracks selection that the app draws,
  which follows the text and copies it over OSC 52.
- **Keys that need the kitty keyboard protocol.** Without it, terminals send Shift+Enter as Enter
  and Ctrl+Backspace as Backspace, so Counterweight can't tell them apart.
  Bind Alt+Enter or Ctrl+J for a line break instead, as [`use_text_area`](headless/use_text_area.md) does.
  Tracked in [#419](https://github.com/JoshKarpel/counterweight/issues/419).
- **Fewer colors.** Counterweight writes every `Color`, including the color utilities' palette, as 24-bit color,
  and ignores `NO_COLOR`, so a terminal limited to 256 or 16 colors shows the wrong ones.
  Use a terminal with 24-bit color (in tmux, turn it on with the `RGB` terminal feature),
  or style with [terminal colors](styles/utilities.md#terminal-colors), which the terminal decides.
  Tracked in [#440](https://github.com/JoshKarpel/counterweight/issues/440).
- **Context.** A value that many components deep in the tree need is passed down through each component's arguments.
  Tracked in [#118](https://github.com/JoshKarpel/counterweight/issues/118).
- **Text width per terminal, and wrapping CJK text.** Counterweight measures each character
  with one table rather than the terminal's own, and terminals disagree about some emoji
  ([#397](https://github.com/JoshKarpel/counterweight/issues/397)),
  and it wraps lines only at spaces, so Chinese and Japanese text is hyphenated wherever it runs out of room
  ([#396](https://github.com/JoshKarpel/counterweight/issues/396)).
- **Graphics protocols.** A `Canvas` draws pixels as half blocks, two to a cell,
  rather than through the kitty or Sixel graphics protocols, so pictures are coarse.
  Tracked in [#441](https://github.com/JoshKarpel/counterweight/issues/441).
- **Windows.** Counterweight reads input through POSIX terminal APIs,
  runs programs on POSIX pseudo-terminals, and is tested on Linux and macOS.

### How mature it is

Counterweight is alpha: its releases are numbered below 1.0,
and its API still changes between them, as the [changelog](changelog.md) records.
It needs Python 3.15 or newer.
