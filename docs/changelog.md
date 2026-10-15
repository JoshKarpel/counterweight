# Changelog

## `0.1.0`

### Added

- [#391](https://github.com/JoshKarpel/counterweight/issues/391)
  Added [headless components](headless/index.md) in `counterweight.headless`,
  starting with [`use_text_input`](headless/use_text_input.md), which edits one line of text and leaves drawing it to its caller.
  The caller owns the value and passes its setter; the hook owns the cursor, makes the component focusable,
  and returns the value split around the cursor with an `on_input` handler for Readline's editing keys and pastes.
  Each edit applies to the latest value through the setter, so keys typed faster than the app renders all land,
  and a setter that validates or transforms edits decides where the cursor goes.
  It returns the cursor as an offset in code points, and a `cursor_cell` element handle that its handler scrolls into view
  with each edit, so a value wider than its box scrolls to keep the cursor in view, as a browser's `<input>` does.
  `counterweight.widgets.text_input` is a bordered box built on it, with a placeholder,
  which scrolls its value inside its border that way, starts scrolled to its end,
  and shrinks beside its siblings rather than growing to fit its value.
  The hook also returns an `on_press` handler for the element the value is drawn in,
  which puts the cursor where a press lands and focuses the field, as a click in a browser's `<input>` does,
  and both widgets use it.

- [#416](https://github.com/JoshKarpel/counterweight/pull/416)
  Added [`use_text_area`](headless/use_text_area.md), which edits text that wraps onto rows and leaves drawing it to its caller.
  It wraps the value itself, at the width the caller gives it, filling each row as text editors do
  and keeping a cell for the cursor wherever it is,
  and returns the rows split around the cursor, so Up and Down (and Ctrl+P and Ctrl+N) move between the rows on screen, keeping their column,
  and Home, End, Ctrl+U and Ctrl+K act on the cursor's row.
  Ctrl+A and Ctrl+E move to the start and end of the row too,
  and pressed again there, go on to the start and end of the value,
  which Ctrl+Home and Ctrl+End reach in one press.
  Ctrl+J inserts a line break, and so does Enter with `enter_inserts_newline=True`;
  otherwise Enter bubbles, as for a form or a chat that submits on it.
  A paste keeps its line breaks and expands tabs to tab stops every `tab_size` columns (4 by default).
  PageUp and PageDown move the cursor a page of rows, scrolling a scroll container by the same page, rather than bubbling.
  Its `on_press` handler puts the cursor where a press lands, as for `use_text_input`.
  Each line's wrapping is cached, so an edit rewraps only the line it changes.
  It returns a `cursor_row` element handle for the element the cursor's row is drawn in,
  which its handler scrolls into view with each edit, so a text area in a scroll container keeps the cursor in view.
  `counterweight.widgets.text_area` is a bordered box built on it, which wraps at its own width
  and grows to fit its rows up to a `max_height`, past which it scrolls, starting scrolled to its end,
  and keeps its height in a column too short for everything in it.
  The [chat](https://github.com/JoshKarpel/counterweight/blob/main/examples/chat.py) example
  sends Markdown messages from a `text_area` to a transcript that sticks to its end as replies stream in.

- [#416](https://github.com/JoshKarpel/counterweight/pull/416)
  Added [`use_scroll_area`](headless/use_scroll_area.md), which scrolls a box with the keys, the wheel and controls,
  and leaves drawing it to its caller, as Radix UI's ScrollArea does for React.
  It makes the component focusable, as browsers make a scroll container focusable, so Tab reaches it,
  and its handler scrolls for the arrows, PageUp, PageDown, Space, Home and End,
  and for the wheel (Shift with it sideways), passing an event on once the area reaches an end,
  and focuses the area for a press nothing inside it claims.
  It returns the style that makes the element that scrolls a scroll container on its `axis` (`"x"`, `"y"` or `"both"`),
  clipping the other axis and sticking to the end with `stick_to_end`, to merge after any constraint utility,
  a `viewport` element handle that a parent can pass in to scroll the area from outside,
  its `scroll`, `is_at_start` and `is_at_end`, and `to_start` and `to_end` controls, as for a "jump to latest" button.
  The element that scrolls can be inside the one that's focused, with a title or a button beside it.
  `counterweight.widgets.scroll_area` is a bordered box built on it, whose border shows focus,
  styled by a `ScrollAreaStyles`.

- [#416](https://github.com/JoshKarpel/counterweight/pull/416)
  Added `counterweight.widgets.TextFieldStyles`, which both widgets take as `styles`,
  for their box while unfocused, focused and unfocusable, their cursor, and their placeholder.
  A widget's `style` merges under the focused and unfocusable styles, so a custom border color doesn't hide which field is focused.

- [#416](https://github.com/JoshKarpel/counterweight/pull/416)
  Added `toggle`, which flips a flag through a `use_state` setter (`set_open(toggle)`),
  so toggles that land before the next render each flip the latest value,
  and a type checker rejects it for state that isn't a `bool`.
  The [`use_state`](hooks/use_state.md#updating-state-from-its-previous-value) docs show how setting state
  from a value computed from the state a render saw loses updates, and when to pass a function instead.

- [#416](https://github.com/JoshKarpel/counterweight/pull/416)
  Mouse events say which modifier keys were held, in `is_shift_held`, `is_alt_held` and `is_control_held`,
  as the DOM's `MouseEvent` does, so a handler can match a Ctrl+click or a Shift+wheel.
  [`scroll_on_wheel`](input-handling/handlers.md#scrolling) scrolls sideways for the vertical wheel with Shift held,
  as browsers on Windows and Linux do, so wide code blocks and tables in [`markdown`](rich-text/markdown.md#wide-code-and-tables)
  scroll without a sideways wheel.
  Some terminals keep Shift with the wheel for their own scrollback and never report it.

- [#415](https://github.com/JoshKarpel/counterweight/pull/415)
  Added [scroll containers](layout/scrolling.md): a box whose overflow is `Scroll`,
  with the utilities `overflow_scroll`, `overflow_x_scroll` and `overflow_y_scroll`,
  shows the part of its content its offset scrolls into view.
  Counterweight holds each container's offset, and after every layout keeps the content in view where it was,
  as CSS's scroll anchoring does, and clamps the offset to how far the content reaches.
  The `overflow_anchor` style field, with `overflow_anchor_auto` and `overflow_anchor_none`, turns anchoring off,
  and the `stick_to_end_x` and `stick_to_end_y` style fields, with `stick_to_end` and `unstick` and their `_x` and `_y` forms,
  keep a container that's scrolled to its end there as its content grows, as a log or a chat transcript wants.
  The controls `ScrollTo` and `ScrollBy` scroll a container named by an `ElementHandle`,
  which an element takes as its `handle`, or by a receiver's `subtree`,
  and `ScrollIntoView` scrolls every container above an element until it's in view,
  as the web's `scrollIntoView` does.
  All three apply in order to the layout of the next render, so they scroll in the same frame as,
  and the content laid out by, any state change returned beside them.
  Moving focus scrolls the newly focused element into view.
  `counterweight.handlers` gains `scroll_on_wheel` and `scroll_on_keys`, which scroll for the wheel
  and for the arrow keys, PageUp, PageDown, Home and End,
  and pass the event on to the container outside once their own reaches an end,
  and `page_down` and `page_up`, which return the `ScrollBy` for a page of any fraction of the view.
  [`use_scroll`](hooks/use_scroll.md) returns how far the calling component's element,
  or the element with a given `ElementHandle`, is scrolled and how far it can be,
  and a `Receiver` carries the same as its `scroll`.

- [#388](https://github.com/JoshKarpel/counterweight/issues/388)
  Added the overflow utilities `overflow_visible`, `overflow_hidden` and `overflow_clip`,
  with `overflow_x_*` and `overflow_y_*` forms that set one axis.
  A box whose overflow is `Hidden`, `Clip` or `Scroll` clips its children to its padding box
  on each axis that sets it, and the mouse reaches an element only where it's painted:
  routing, `use_hovered` and `on_click` ignore the parts of an element its ancestors clip away.
  The constraint utilities (`length`, `percentage`, `ratio` and `fill`) hide their box's overflow.
  The `clip_to` style field, with `clip_to_padding`, `clip_to_border` and `clip_to_screen`,
  which lets a child such as a border title draw on its parent's border when its parent clips,
  or a popup such as a dropdown escape every clip above it.
  `Rects` gains `clip`, the region an element's ancestors let it draw in,
  and `visible`, the part of its border box inside that region.
  See [Clipping](layout/clipping.md), and the [autocomplete recipe](cookbook/autocomplete.md).

- [#330](https://github.com/JoshKarpel/counterweight/issues/330)
  Added [`markdown_document`](rich-text/markdown.md), a component that renders a Markdown document
  (GitHub Flavored Markdown, with its task lists, alerts, footnotes, bare URLs, and math, and YAML front matter),
  styled by a `MarkdownStyles` with a field for each kind of block and span.
  It's a `memo` component, which parses its document again only when its arguments change,
  and `markdown`, the function it calls, returns the document as a `Div` of elements.
  Links are hyperlinks, and fenced code blocks and front matter are highlighted.
  Code blocks and tables too wide for the space they're given scroll sideways with the wheel, as GitHub's styles scroll them,
  and a table wraps its cells as narrow as their words allow before it scrolls.
  `keeps_line_breaks=True` keeps each line break inside a paragraph, as GitHub's comments and chat apps do.
  The [Markdown viewer](https://github.com/JoshKarpel/counterweight/blob/main/examples/markdown_viewer.py) example
  shows a directory's Markdown files beside a tree of them, and the
  [Markdown gallery](https://github.com/JoshKarpel/counterweight/blob/main/examples/markdown_gallery.py) example
  shows each kind of block and span beside its source, which you can edit to see the result change.

- [#330](https://github.com/JoshKarpel/counterweight/issues/330)
  Added [syntax highlighting](rich-text/syntax-highlighting.md) with Pygments:
  `highlight` returns code as styled chunks, `code_style` its theme's background and text color,
  and `code_block` a `Text` of the highlighted code on that background.

- [#330](https://github.com/JoshKarpel/counterweight/issues/330)
  Added `link` to `CellStyle`, which makes any `Chunk` or `Text` a [hyperlink](rich-text/hyperlinks.md)
  that the terminal opens when it's clicked.

- [#411](https://github.com/JoshKarpel/counterweight/issues/411)
  Added the `SetTitle` control, which sets the title of the terminal window,
  and the `title` argument to `app`, which sets it when the app starts.
  The app saves the title it started with and restores it when it quits and while it's suspended,
  on terminals that support xterm's title stack,
  and the `RestoreTitle` control brings it back while the app runs.

- [#402](https://github.com/JoshKarpel/counterweight/pull/402)
  Added [`use_focus`](hooks/use_focus.md), which makes a component focusable, so that key presses go to it while it's focused.
  It takes `auto_focus`, to take focus on mount when nothing else has it;
  `handle`, a `FocusHandle` a parent creates to focus a child it renders;
  `is_focusable=False`, to disable it; and `in_focus_order=False`, to leave it out of Tab order.
  The controls `FocusNext`, `FocusPrevious`, `FocusOn(handle)` and `ClearFocus` move focus,
  and `FocusNext` and `FocusPrevious` take a `within` subtree to move only inside one element.
  `counterweight.handlers` gains `tab_focus`, `focus_receiver_on_press`, `focus_on_press` and `clear_focus`,
  which return them for Tab and for presses; nothing moves focus unless a handler does.
  A `Receiver` carries the element's `focus_handle`, whether it `is_focused`, and its `subtree`.

- [#402](https://github.com/JoshKarpel/counterweight/pull/402)
  Added `counterweight.handlers`, with `on_click(action)`, which calls `action` when a press on its element
  is released inside it, and `first` and `each`, which compose several handlers into the one an element takes.
  A handler can return a tuple of controls, applied in order and skipping any `None`,
  or `()` to stop an event with nothing more to do.

- [#402](https://github.com/JoshKarpel/counterweight/pull/402)
  Added `inset(n)`, `inset_x(n)` and `inset_y(n)`, which set all four, the left and right, or the top and bottom insets;
  `inset_sides`, `margin_sides` and `pad_sides`, which set each side separately in the order of CSS's four-value shorthands;
  and `auto` margins for every side and pair of sides, from `margin_auto` to `margin_right_auto`.
  `position_absolute | inset(0) | margin_auto | fit_content_width | fit_content_height`
  centers a box over its parent at its own size, as in CSS.

- [#400](https://github.com/JoshKarpel/counterweight/issues/400)
  Added [`use_clock`](hooks/use_clock.md), which gives a component the time
  (the wall-clock time, and how long since the app started and since the component mounted)
  while it stays pure: it re-runs when its next tick starts, ticks follow the wall clock,
  and components reading it in the same frame see the same time.
  `app` takes a `clock` to read the time from, such as a `frozen_clock` for tests and screenshots,
  and the `AdvanceClock` control moves it forward.
  The cookbook shows how to [animate a spinner](cookbook/spinners.md) with it.

- Added [`use_controls`](hooks/use_controls.md), which gives a component a sender that hands the app a control
  from outside an input handler, such as an effect that quits when a program exits.
  The app handles a sent control as it handles one a handler returns, after the events already waiting.

- [#394](https://github.com/JoshKarpel/counterweight/pull/394)
  Added `@component(memo=True)`, which skips re-running a component when its parent re-runs
  and passes it arguments equal to the previous render's,
  and `check_purity` on `app`, which runs every component again after each render
  and raises `ImpureComponent` when that builds something different,
  because a component depends on more than its arguments and hooks.

- [#394](https://github.com/JoshKarpel/counterweight/pull/394)
  Added `use_memo`, which caches a value until its dependencies change,
  so a component can keep an expensive derived value, an unchanging part of its output,
  or a handler it passes to a `memo` component.
  With `check_purity` on, a cached value that a dependency missing from its list would change raises `StaleMemo`.

- Documented how to find where a frame's time goes, which components a frame re-runs,
  and how to skip the rest with `memo=True` and `use_memo`, with their failure modes,
  in [Performance](performance.md).

- Documented how Counterweight compares with Textual, Ink and Ratatui,
  and what it doesn't do, in [Ecosystem](ecosystem.md).

- Documented how components keep their state across renders,
  and how to use keys to move or reset that state.

- Documented that a component must call the same hooks in the same order on every render,
  and how to move a hook that is only sometimes needed into a child component.

- Documented what [`use_ref`](hooks/use_ref.md) is for,
  and why a component shouldn't read or write a ref while rendering.

- Documented how to make a component draggable and keep it inside its parent,
  in [Draggable Components](cookbook/draggable-components.md).

- Documented every style utility on the [utilities page](styles/utilities.md),
  grouped by family: what each constant sets, each function's signature,
  and the color palette.

- [#318](https://github.com/JoshKarpel/counterweight/pull/318)
  Added three text wrapping modes for `Text` elements: `text_wrap_stable` (greedy),
  `text_wrap_balance` (equalizes line lengths), and `text_wrap_pretty` (Knuth–Plass DP,
  minimizes ragged lines). The default remains `text_wrap_none` (no wrapping).
  Words longer than the available width are broken with a hyphen.
  A wrapping `Text`'s minimum size is its widest word, so wrapping `Text`s side by side
  in a row shrink to share it.

- Added the [`Canvas`](elements/canvas.md) element, a leaf whose content box its painter draws cell by cell,
  skipping the text layout a `Text` of chunks goes through every frame.
  It's sized as an `<img>` is: its painter's natural size is its intrinsic size, which it takes on each axis
  its style and its parent's layout leave undetermined, and a painter that keeps its aspect ratio gives a canvas
  sized on one axis the other by that ratio.
  A painter is any object with a `natural_size`, `keeps_aspect_ratio` and `draw(width, height)`,
  which returns rows of styled graphemes whose unset styles come from the canvas;
  a canvas draws again only when its painter isn't equal to the last one or its box changes size.
  `counterweight.painters.pixels` holds `Pixels`, a picture as RGBA bytes,
  which `Pixels.from_image` makes from an image decoded by [Pillow](https://pillow.readthedocs.io/), a new dependency,
  and `HalfBlocks`, a painter that draws one two pixels to a cell with `▀`,
  scaling and placing it as CSS's `object-fit` and `object-position` do,
  and whose `pixels_at` finds the pixels a cell shows, for mouse input.

- Added `counterweight.emulator`, a terminal emulator ([libghostty-vt](https://ghostty.org), through [pyghostty](https://github.com/AnswerDotAI/pyghostty), a new dependency)
  that turns the bytes a program writes into what its terminal shows.
  An `Emulator` is fed bytes, answers the program's queries through `on_reply`, and snapshots into immutable `Screen` values:
  rows of styled graphemes, the cursor, the title, and the modes that change how the program's input is encoded.
  A snapshot of an unchanged terminal is the same `Screen`, and rows that didn't change are shared between snapshots.
  An emulator given a `scrollback` keeps that many rows that scrolled off the top of its screen,
  and `scrolled_off` returns those that scrolled off since it was last called, each once.
  `counterweight.painters.terminal.ScreenView` is the `Canvas` painter that draws a `Screen`,
  leaving the program's default colors to the canvas's `text_style`, and drawing the cursor when asked.
  A program's palette colors stay palette entries, so they follow the user's theme,
  except an entry the program changed, which is the color it changed it to.
  See [Emulators and Pseudo-Terminals](terminals/emulators.md).

- Added colors the terminal decides, which follow the user's theme:
  `IndexedColor(n)`, entry `n` of the terminal's 256-color palette,
  and `TERMINAL_DEFAULT`, the terminal's default foreground where it colors text and default background where it fills one.
  Every style field that took a `Color` takes either (`AnyColor`),
  and the `*_indexed(n)` and `*_terminal_default` utilities set them wherever the color utilities do.
  Screenshots draw palette entries in `DEFAULT_PALETTE` and the defaults as white on black.
  See [Terminal colors](styles/utilities.md#terminal-colors).

- Added `counterweight.pseudoterminal`, which runs a program on a pseudo-terminal, as a terminal window does,
  and hands back the bytes it writes, standard output and standard error together.
  `run_pty` runs one until it exits, returning `Exited` with its status, or `FailedToStart` with the reason,
  such as for an `argv` that doesn't exist, and hands out a `PtyConnection` that writes to the program
  without blocking, buffering what it isn't reading yet, and resizes its terminal, which sends it `SIGWINCH`.
  Its standard input is the terminal, or `/dev/null` for a program that shouldn't wait for keys.
  `use_pty` runs one while its component is mounted, starting it once its size is positive,
  so a terminal sized from `use_rects` starts at its real size rather than 0 by 0,
  resizing it as its size changes, and starting it again when its `argv` or environment change.
  A program gets the app's environment without `COLUMNS` and `LINES`, which describe the app's terminal,
  then `TERM=xterm-256color` and `COLORTERM=truecolor`, then the caller's `env`, or only the last two with `clear_env`.
  Cancelled, or once the program exits, its process group is hung up as closing a terminal window does,
  with `SIGHUP`, then `SIGTERM` and `SIGKILL` a `hangup_grace` apart for whatever ignores it,
  so nothing it started outlives it, even a background job holding the terminal open.

- Added [one-shot commands](terminals/commands.md) in `counterweight.commands`:
  running a program that's expected to exit, and showing everything it printed, colors and all,
  as a terminal would have shown it.
  `use_command` runs one when its `run` is called, on a pseudo-terminal `columns` wide (waiting until that's positive,
  so it can come from `use_rects`) and `rows` tall, with standard input on `/dev/null`
  and `PAGER` and `GIT_PAGER` set to `cat`, and returns the latest run, a `CommandRun` value
  whose output updates at most once a frame while the program runs,
  and whose outcome is `Starting`, `Running`, `Exited`, `FailedToStart`, `Cancelled` or `TimedOut`.
  `cancel`, another `run`, a `timeout`, and unmounting hang the program up.
  A run's output is a `counterweight.painters.terminal.Transcript`, a `Canvas` painter as wide as the run's terminal
  and as tall as the lines it printed: the rows that scrolled off its screen, then the screen,
  keeping the last `max_lines`, and `Transcript.of` builds one from output recorded ahead of time.
  `command_output` shows a run in a `scroll_area` that follows its end, with its outcome beneath.
  The [slides](https://github.com/JoshKarpel/counterweight/blob/main/examples/slides.py) example
  runs a command on each slide when it's shown.

- Added [embedded terminals](terminals/embedding.md): running an interactive program, such as a shell or an editor,
  in a box that shows its screen and sends it the input the box receives, as a multiplexer's pane does.
  `counterweight.headless.use_terminal` runs one on a pseudo-terminal while its component is mounted,
  emulates its terminal, snapshotting it at most once a frame, and makes the component focusable,
  returning the `Screen`, a `ScreenView` painter that draws the cursor while focused, the program's status,
  and an `on_input` handler for the `Canvas` the component draws it in.
  While focused, the handler sends the program every key press and paste, Ctrl+C included,
  and the mouse events it asked for, encoded as xterm sends them for the modes the program set,
  and a program that asked gets focus events as the component gains and loses focus.
  A handler put before it with `first` takes keys first, as a prefix key does.
  `counterweight.widgets.terminal` is a bordered box built on it, sized by its `style`,
  whose `intercept` handler sees each event before the program does.
  `counterweight.input_encoding` holds the pure functions that encode key presses, pastes, mouse events and focus changes
  back into a terminal's bytes, built from the input parser's own tables.
  The [multiplexer](https://github.com/JoshKarpel/counterweight/blob/main/examples/multiplexer.py) example
  runs shells side by side with a tmux-style prefix, showing the keys that follow it along the bottom, as zellij does,
  and closes a pane when its shell exits.

- Added [running programs on the app's terminal](terminals/programs.md), as `git commit` runs an editor.
  `Suspend.to_program` suspends the app, runs a program on the app's `input_stream` and `output_stream`
  until it exits, with the app's environment and `env` (or only `env` with `clear_env`) in `cwd`,
  and calls `on_exit` with `Exited` or `FailedToStart`.
  While it runs, the app swallows `SIGINT` and `SIGQUIT`, as POSIX's `system()` does,
  so Ctrl+C in a pager reaches the pager without quitting the app.
  `Suspend.to_edit_file` opens a file in the user's editor, `$VISUAL`, then `$EDITOR`, then `vi`,
  and calls `on_exit` with how the editor exited.
  `Suspend.to_edit_text` edits a string the same way, through a file whose name sets the editor's highlighting,
  and calls `on_edit` with the edited text, or with how the editor failed, so vim's `:cq` abandons the edit.
  `counterweight.programs` holds the functions they run,
  `run_program`, `edit_file`, `edit_text` and `preferred_editor`,
  and `Exited` and `FailedToStart`, which `run_pty` returns too.

- `app` takes `unclaimed_keys`, what a key press does when no handler on its path claims it,
  as a browser takes a key's default action unless a listener prevents it.
  `DEFAULT_UNCLAIMED_KEYS` gives Ctrl+C `Quit` and Ctrl+Z `Suspend.to_shell()`,
  which suspends the app as a shell job until the shell resumes it with `fg`,
  stopping its whole process group as the terminal's Ctrl+Z does, so `uv run` and the like stop with it.
  Pass `{}` for no defaults, or merge onto them to change some.
  See [Keys the terminal would act on](input-handling/events.md#keys-the-terminal-would-act-on).

- Added `Key.ControlBackslash`, `Key.ControlRightBracket`, `Key.ControlCaret` and `Key.ControlUnderscore`,
  and their Ctrl+Alt forms, so every control byte a terminal sends is a key.
  Previously Ctrl+\\, Ctrl+], Ctrl+^ and Ctrl+_ were skipped.

- Added a [Prefix Keys](cookbook/prefix-keys.md) cookbook page: a tmux-style prefix key,
  kept in a ref so a prefix and its key typed together still work,
  and a pane it opens focused with `FocusOn`.

- [#305](https://github.com/JoshKarpel/counterweight/pull/305)
  Added `clamp(min_, val, max_)` to `counterweight.utils` for clamping numeric values to a range.

- [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  Added `counterweight.styles.merge`, which merges any number of `Style`s left to right,
  as an alternative to chaining `|`: `merge(a, b, c)` is `a | b | c`.
  It skips `None` arguments wherever they appear.

- [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  Added the sizing keyword utilities `min_content_width`, `max_content_width`,
  `fit_content_width` and `stretch_width`, and their `_height` counterparts,
  which size a box from its content or fill the space available after its margins.

- [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  Added the constraint utilities `length(n)`, `percentage(p)`, `ratio(a, b)` and `fill(n)`,
  which split space along the parent's main axis the way ratatui's constraints of the same names do:
  a child takes its share whatever its content, in a `row` or a `col`.
  For grid, `fr(n)` is a track of `n` shares that content can't widen (`minmax(0, n fr)`),
  and `span(n)` places a child across `n` tracks.
  `grid_template_columns` and `grid_template_rows` accept a plain `int` as a track of that many cells,
  and `grid_row` and `grid_column` accept one as a grid line.
  `center_children` centers children on both axes.

- [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  Added `Screenshot.to_stream`, which prints a screenshot as a text grid
  (with or without ANSI escape codes), useful for debugging layout and in tests.

- [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  Added a Layout section to the documentation:
  a guide to choosing between flexbox and grid,
  and a gallery of layout effects, each shown as code beside its screenshot,
  with every screenshot also available as copyable text.

- [#305](https://github.com/JoshKarpel/counterweight/pull/305)
  New functional style utilities: `pad(n)`, `pad_x(n)`, `pad_y(n)`, `pad_top(n)`, etc.;
  `margin(n)`, `margin_x(n)`, `margin_y(n)`, `margin_top(n)`, etc.;
  `gap(n)`, `gap_width(n)`, `gap_height(n)`;
  `size(w, h)`, `grow(n)` (which sets only `flex_grow`);
  `inset_top(n)`, `inset_bottom(n)`, `inset_left(n)`, `inset_right(n)`;
  `full`, `full_width`, `full_height`, which fill the parent after the box's margins.

- [#305](https://github.com/JoshKarpel/counterweight/pull/305)
  New style utilities `position_absolute` and `position_relative` replace the old
  `absolute(x, y)`, `relative(x, y)`, and `fixed(x, y)` helpers.
  Offsets are now expressed with `inset_left(n)` / `inset_top(n)` (and friends) instead of `x`/`y` arguments.

- [#305](https://github.com/JoshKarpel/counterweight/pull/305)
  Color style utilities (e.g. `text("slate", 500)`, `border_bg("blue", 300)`,
  `content_color("green", 500)`, `margin_color("red", 600)`) now use functional helpers
  instead of per-shade constants, greatly reducing the size of the generated utilities module.

- [#123](https://github.com/JoshKarpel/counterweight/pull/123)
  Add styling for content area background color.

### Changed

- A `Suspend` handler receives the terminal the app handed back, as `TerminalStreams`,
  so it can run a program on the terminal the app draws on even when that isn't standard output.
  A handler that took no arguments takes one now.

- The app reads the terminal raw, as tmux does, so Ctrl+C, Ctrl+Z, Ctrl+\\, Ctrl+S and Ctrl+Q reach it as key presses
  rather than the terminal acting on them.
  Ctrl+C still quits, now as its [unclaimed default](input-handling/events.md#keys-the-terminal-would-act-on),
  so a handler that claims it keeps it, such as to cancel a command.
  Previously Ctrl+Z and Ctrl+\\ stopped and killed the app without handing the terminal back,
  and Ctrl+S froze its output until Ctrl+Q.
  An interrupt sent from outside, with `kill -INT`, still quits it, and a second one still reaches the handler it replaced,
  but an app whose render loop is stuck can no longer be quit with Ctrl+C, since nothing reads it.

- [`FocusOn`](hooks/use_focus.md#focusing-a-component-as-it-mounts) focuses a component that mounts
  in the render its handler causes: one whose handle no component can take focus with yet
  waits for the next render, and focuses it before the frame is drawn, unless another control moves focus first.
  Previously it did nothing, so a handler that added a component had to clear focus for its `auto_focus`.

- [`use_rects`](hooks/use_rects.md) takes an optional `ElementHandle`, and reports the rectangles of the element
  with that handle rather than the calling component's own, as a React component measures an element through a ref,
  so a component can measure an element a child component draws.
  A component that calls it renders again as soon as any of the rectangles it read move, as one that calls `use_scroll` does.
  Previously it rendered again only once something else started a render,
  so a component that mounted after the first frame read empty rectangles until then.

- [#416](https://github.com/JoshKarpel/counterweight/pull/416)
  **Breaking:** a `Text` overflows its box, as CSS's text does:
  a line wider than its content box runs past it, and rows below its height draw below it,
  until an ancestor whose overflow is `Hidden`, `Clip` or `Scroll` cuts them off, or the `Text`'s own overflow does.
  Previously every `Text` cut its lines off at its own box, though layout counted them,
  so a long line in a scroll container scrolled into blank space unless the `Text` was as wide as the line.
  A `Text` that should cut its text off at its box takes `overflow_hidden`, as the constraint utilities already set.

- [#416](https://github.com/JoshKarpel/counterweight/pull/416)
  **Breaking:** keys pressed with Alt, which terminals send as `ESC` and then the key, arrive as one key press:
  `Key.AltEnter`, `Key.AltBackspace`, `Key.ControlAltA` and the other Ctrl+Alt letters,
  `Key.AltUp` and the other navigation keys, `Key.AltF1` through `Key.AltF12`,
  and `"alt+"` before the text for text, such as `"alt+b"`.
  Previously they arrived as Escape and then the key.
  A text area inserts a line break on Alt+Enter, and `use_text_input` and `use_text_area` take
  Readline's Alt+B, Alt+F, Alt+D and Alt+Backspace, with Alt+Left, Alt+Right and Alt+Delete, to move and delete by word.

- [#416](https://github.com/JoshKarpel/counterweight/pull/416)
  **Breaking:** Ctrl+J is `Key.ControlJ`, rather than `Key.Enter`.
  The app stops the terminal turning the carriage return Enter sends into a line feed,
  so the two keys arrive as different `KeyPressed` events, and a text area can take Ctrl+J for a line break.

- [#391](https://github.com/JoshKarpel/counterweight/issues/391)
  **Breaking:** the app turns on the terminal's bracketed paste mode,
  so pasted text arrives as one [`Pasted`](input-handling/events.md#handling-pastes) event holding all of it,
  routed to the focused element like a key press, with its line breaks as `"\n"`.
  Previously it arrived as key presses, and its line breaks as Enter.
  `counterweight check-input` shows pastes too.

- [#415](https://github.com/JoshKarpel/counterweight/pull/415)
  `Rects` is keyword-only, since it has more fields than are easy to keep in order.

- [#414](https://github.com/JoshKarpel/counterweight/pull/414)
  **Breaking:** a `Div`'s `children` is a tuple, and so is a `Text`'s `content` when it's chunks,
  so an element is a value that can be cached and shared without anything changing it afterwards.
  Pass `(a, b)` or `tuple(...)` where you passed a list.

- [#414](https://github.com/JoshKarpel/counterweight/pull/414)
  `Color.from_hex` accepts the CSS shorthand `#rgb` as well as `#rrggbb`,
  and raises `ValueError` for any other number of digits
  instead of dropping the extra digits of a color like `#rrggbbaa`.

- [#414](https://github.com/JoshKarpel/counterweight/pull/414)
  SVG screenshots draw text that is bold, dim, italic, underlined, or struck through,
  instead of drawing it plain.

- [#176](https://github.com/JoshKarpel/counterweight/issues/176)
  Each frame is written as one [synchronized update](https://github.com/contour-terminal/vt-extensions/blob/master/synchronized-output.md),
  so terminals that support it show the whole frame at once instead of tearing partway through drawing it,
  and redrawing the screen after a resize or a suspension no longer flashes it blank first.

- [#402](https://github.com/JoshKarpel/counterweight/pull/402)
  **Breaking:** a key press goes to the focused element, or to the root component's element when nothing is focused,
  then bubbles through its ancestors until a handler returns something other than `None`.
  Previously every handler received every key press, whatever the others returned.
  A component that handles keys below the root calls `use_focus`, with `auto_focus=True` to have keys from the start,
  and puts its handler on the element it returns;
  one that should act on keys wherever focus is moves its handler to the root component's element.
  Tab has no built-in meaning: put `tab_focus` on the root for Tab navigation.

- [#402](https://github.com/JoshKarpel/counterweight/pull/402)
  **Breaking:** a mouse event goes to one target, the element drawn on top at the pointer,
  then bubbles through its ancestors until a handler returns something other than `None`.
  A press runs from the first button going down to the last coming up,
  and is captured by the element whose handler stops its first `MouseDown`:
  its moves, and every button's presses and releases while it lasts, go to that element alone,
  wherever the pointer is, and reach no handler if nothing stopped the first `MouseDown`.
  Previously every element under the pointer's current or previous position received every mouse event,
  so a drag that outran a render lost its element.
  A handler that acts on a release or a drag returns `()` for the `MouseDown`,
  or uses `on_click`, and one that acts on any mouse event returns `()` to keep its ancestors from acting on it too.

- [#402](https://github.com/JoshKarpel/counterweight/pull/402)
  `z` follows CSS's stacking contexts.
  An element that sets `z`, `z(0)` included, paints with its descendants as one layer at its `z`,
  and its descendants' `z` orders them only among each other,
  while an element that sets no `z` leaves its descendants to be layered alongside it.
  Previously every element was sorted by `z` in one flat order,
  so an element with a higher `z` than its children painted over them,
  and an element with a negative `z` painted beneath every element, its own parent included;
  now children always paint over their parent, and a negative `z` paints beneath the rest of its stacking context
  but over the element that forms it.
  An app that sets `z` on nested elements may layer differently.
  `STYLE_DEFAULTS.z` is `None`, for an element that sets no `z`, rather than `0`.

- [#402](https://github.com/JoshKarpel/counterweight/pull/402)
  An element's margin is painted only where its style sets `margin_color`,
  and its `content_color` fills its border box rather than its margin box,
  so a margin leaves whatever lies beneath it visible, as on the web.
  Previously every margin painted black over what was beneath it,
  so an absolutely positioned box with large margins blanked out its parent.

- [#402](https://github.com/JoshKarpel/counterweight/pull/402)
  **Breaking:** `Div` and `Text` take one `on_input` handler in place of `on_key` and `on_mouse`.
  It receives both key presses and mouse events, so one `match` case can handle `Down` and the scroll wheel alike,
  and a `Receiver` describing the element, whose `rects` and `relative` locate a mouse event inside it,
  and whose `is_target` tells the event's target from an ancestor it bubbled to.
  A handler that takes only the event, or annotates it as `KeyPressed` or `MouseEvent`, fails to type-check;
  annotate it as `InputEvent` and match on the event's class.
  `Rects` lives in `counterweight.geometry`, and `counterweight.hooks` still exports it.

- Cancelling the task running `app` raises `CancelledError` out of it once the terminal is restored,
  as asyncio expects, so `asyncio.timeout` and `wait_for` around an app can tell it was cancelled.
  Previously `app` returned as if the app had quit.
  Pressing ctrl+c still quits the app and `app` returns,
  so an app run with `asyncio.run` exits without a traceback.
  A second ctrl+c, before a stuck app has quit, goes to the interrupt handler `app` replaced,
  which for `asyncio.run` cancels the app and raises `KeyboardInterrupt`.

- [#271](https://github.com/JoshKarpel/counterweight/issues/271)
  `app` takes the root component already called, as `app(root())` rather than `app(root)`,
  so a root component can take arguments like any other: `app(root(Path(sys.argv[1])))`.

- [#394](https://github.com/JoshKarpel/counterweight/pull/394)
  An error raised while the app runs, in a component, a handler or an effect,
  propagates out of `app` as itself rather than wrapped in an `ExceptionGroup`,
  after the terminal is restored, so its traceback ends at the line that raised it
  and callers can catch it by its own type.
  Errors raised at the same moment from more than one effect are still grouped.

- [#394](https://github.com/JoshKarpel/counterweight/pull/394)
  A render calls only the components whose state changed and the components they return,
  instead of every component, and keeps the previous render's output for the rest.
  An effect with `deps=None` runs after every render of its own component,
  rather than after every render of the app.

- [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  The `*_center` and `*_end` alignment utilities
  (`justify_children_*`, `align_children_*`, `align_self_*`, `justify_items_*`, `justify_self_*`)
  use CSS's safe alignment: content too large for its container starts at the start edge
  instead of overflowing past it.
  Each has an `*_unsafe` counterpart, such as `justify_children_center_unsafe`,
  that centers or end-aligns overflowing content anyway.

- [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  **Breaking:** a `Screenshot` handler now receives a `counterweight.output.Frame`
  instead of an SVG `ElementTree`; call `frame.svg()` or `frame.text()` to encode it.
  `Screenshot.to_file` chooses the encoding from the path's suffix
  (`.svg` for SVG, `.txt` for text with ANSI escape codes),
  always indents SVGs, and no longer takes `indent`.
  Every `Screenshot` requested in the same render cycle now receives the same frame,
  where previously only the last one ran.

- The setter returned by `use_state` is the same object on every render of a component,
  so including it in an effect's `deps` no longer reruns the effect each render.

- Calling a `use_state` setter after its component has unmounted does nothing,
  instead of updating orphaned state and triggering a render that changes nothing.

- **Breaking:** A component that calls a different number of hooks than on its previous render
  raises `InconsistentHookExecution`.
  Skipping a trailing hook used to pass silently, and a skipped `use_effect` kept running.

- **Breaking:** Keyed sibling components that share a key raise `DuplicateKey`.

- **Breaking:** Component keys are strings only; `with_key` no longer accepts an `int`.
  Convert numeric ids with `str()`.

- [#318](https://github.com/JoshKarpel/counterweight/pull/318)
  **Breaking:** `Key.Space` now has the string value `" "` instead of `"space"`.
  Code that matched on the string value (e.g. `event.key == "space"`) must be updated;
  matching on the enum member (`Key.Space`) is unaffected.

- [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  **Breaking:** borders work as they do in Tailwind.
  A border side is drawn where its width in `Style.layout` is 1, and `border_kind` only chooses the characters.
  `border_kind` defaults to `BorderKind.Light`, so the new `border` utility alone draws a light border,
  and the `border_<kind>` utilities no longer reserve space or draw anything on their own:
  write `border | border_heavy` where you wrote `border_heavy`.
  `border_top`, `border_bottom`, `border_left` and `border_right` set one side, the new `border_x` and `border_y`
  set a pair, and each has a new `_0` form (`border_0`, `border_top_0`, ...) that clears its sides.
  A `border_kind` of `None` (`border_none`) removes the border along with the space reserved for it.
  A border width in `Style.layout` other than `Length(0)` or `Length(1)` raises `ValueError`.
  `border_all` and the edge combinations such as `border_top_left` are removed:
  use `border`, or compose sides as in `border_top | border_left`.

- [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  Every field of `Style` (except `layout`) and `CellStyle` starts out as the new
  `counterweight.styles.UNSET` sentinel rather than its default value,
  so reading a field of a style you built can return `UNSET`.
  The defaults live in `counterweight.styles.STYLE_DEFAULTS` and `counterweight.styles.CELL_STYLE_DEFAULTS`,
  and fill unset fields when an element is drawn.

- [#315](https://github.com/JoshKarpel/counterweight/pull/315)
  Core types (`Style`, `CellStyle`, `Div`, `Text`, `Chunk`, hook types) have been converted
  from Pydantic models to frozen `dataclass` instances, removing the runtime Pydantic dependency.

- The `counterweight` CLI is built on [without-cli](https://www.without.help/without-cli/),
  so counterweight no longer depends on typer, click, rich or shellingham.
  `counterweight` with no command prints a short usage error instead of the full help,
  `counterweight --version` prints the version as `counterweight version` does,
  and shell completion (`--install-completion`) is gone.

- [#305](https://github.com/JoshKarpel/counterweight/pull/305)
  The layout engine has been replaced with [waxy](https://github.com/JoshKarpel/waxy),
  a Python binding for the [taffy](https://github.com/DioxusLabs/taffy) flexbox/grid layout engine.
  This brings standard CSS flexbox semantics, improved correctness for complex layouts,
  and eliminates the hand-rolled layout engine.

- [#305](https://github.com/JoshKarpel/counterweight/pull/305)
  `use_rects` now returns `counterweight.geometry.Region` objects instead of the removed `counterweight.geometry.Rect`.
  A `Region`'s `right` and `bottom` are exclusive (the first column and row outside it),
  so `width` and `height` count cells, and its corner properties (e.g. `top_left`) are `Position`s.

- [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  **Breaking:** counterweight logs through the standard library's `logging`, and no longer depends on
  or configures structlog. While an app runs, its log records
  (`logging.getLogger(__name__).debug("...", extra={...})`) are written to the devlog off the render loop
  by [without-logging](https://www.without.help/without-logging/),
  by default, counterweight's and the app's own at every level (the app's being the top-level package
  of the module that defines its root component), and every other logger's from `INFO` up,
  so a library that logs at `DEBUG` on a hot path costs nothing unless an app asks for its records.
  `app`'s `log_levels` sets levels by logger name, as `logging.config` does, over those defaults.
  The devlog is a single JSON-lines file, which `counterweight devlog` renders for reading
  (`--json` prints the raw lines). Its messages no longer carry `elapsed_ns` timings:
  to see where a frame's time goes, profile the app with Python's sampling profiler
  (`python -m profiling.sampling run app.py`).

- [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  Laying out a frame costs less. An app keeps one layout tree for its lifetime,
  so taffy reuses the layout of every element whose style, text and children are unchanged,
  and a `Text` is wrapped at most once per width it is measured at.

- [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  Painting a frame costs less. Elements paint straight into one screen-sized grid of cells,
  a row at a time, and an element's text and border are cached wherever it moves on the screen.
  Only the cells that changed since the last frame are written to the terminal,
  with one cursor move per run of changed cells and a style change only where the style changes.
  Building a `CellStyle` or cell equal to one built recently returns the cached instance.

- [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  Merging styles with `|` costs less: a `Style` computes its hash once, when it's built,
  and merges are cached with `functools.lru_cache`. counterweight no longer depends on cachetools.

- [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  **Breaking:** `Frame.paint` is a `counterweight.paint.Paint`, a screen-sized grid of cells,
  rather than a `dict` from `Position` to cell.
  Index it with a `Position` or an `(x, y)` pair, or read it a row at a time with `rows()`.

- [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  The painted cell `counterweight.paint.P` is renamed `Cell`, and its `char` is renamed `grapheme`.
  It is a frozen dataclass of a grapheme cluster and its resolved style, and no longer carries its element's `z`.
  `counterweight.elements.CellPaint`, a grapheme cluster and its unresolved `CellStyle`,
  is renamed `StyledGrapheme`, and its `char` is renamed `grapheme`.

### Fixed

- [#407](https://github.com/JoshKarpel/counterweight/issues/407)
  Terminal input is parsed incrementally, so typed and pasted text arrives intact:
  - Text beyond ASCII is decoded as UTF-8, one `KeyPressed` per grapheme cluster (`"é"`, `"日"`).
    Previously it was dropped, along with everything else read alongside it.
  - An escape sequence Counterweight doesn't recognize (such as Ctrl+digit in some terminals)
    is skipped. Previously it arrived as an Escape key press followed by its characters.
  - An escape sequence or UTF-8 character split between two reads is held over and completed by the next one,
    and a lone `ESC` is the Escape key once no more input follows for 50 milliseconds.
    Previously a split sequence turned into stray key presses, most often during a flood of mouse motion.
  - A carriage return is `Key.Enter`.

  `parsy` is no longer a dependency.

- [#402](https://github.com/JoshKarpel/counterweight/pull/402)
  Scrolling the mouse wheel up is reported as `MouseScrolledUp` and down as `MouseScrolledDown`,
  as xterm defines them; previously the two were swapped.
  The mouse wheel scrolled with Shift, Alt or Control held is reported as a scroll,
  and the horizontal wheel as `MouseScrolledLeft` and `MouseScrolledRight`, new events.
  Previously all of these were reported as presses of buttons 1 to 3,
  so a sideways trackpad swipe clicked whatever was under the pointer.
  Buttons 8 to 11, such as back and forward, are reported by their own numbers
  rather than as buttons 1 to 4.

- [#402](https://github.com/JoshKarpel/counterweight/pull/402)
  Home, Page Up and Page Down are reported, as the new `Key.Home`, `Key.PageUp` and `Key.PageDown`,
  and so is every key the `Key` enum names with Shift, Control, or both,
  such as `Key.ShiftHome`, `Key.ControlPageDown` and `Key.ControlF5`,
  with Shift and F1 to F12 reported as F13 to F24, as xterm does.
  Previously only the arrow keys were reported with modifiers.
  Control+Shift+Delete is reported as `Key.ControlShiftDelete` rather than `Key.ControlShiftInsert`.
  **Breaking:** `Key.ControlSpace` is `"ctrl+space"`, like every other key, rather than `"ctrl-space"`.

- [#392](https://github.com/JoshKarpel/counterweight/issues/392)
  Text is measured, wrapped and painted by grapheme cluster and its display width, as measured by
  [wcwidth](https://github.com/jquast/wcwidth), a new dependency,
  so CJK characters and emoji take two cells and no longer push the rest of their line out of place,
  combining marks and joined emoji (`👩‍💻`) stay whole,
  and zero-width characters such as zero-width spaces take no cells.
  `StyledGrapheme.width` is the number of cells a cluster takes.
  See [wide characters](elements/text.md#wide-characters).

- [#392](https://github.com/JoshKarpel/counterweight/issues/392)
  Control characters in text other than line breaks, such as tab and escape,
  are drawn as symbols (`␉`, `␛`) rather than written to the terminal, where they ran as commands.

- [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  Merging styles with `|` now lets the right side override the left with a default value:
  `border_heavy | border_none` has no border kind, `text_justify_center | text_justify_left` justifies left,
  `z(5) | z(0)` has `z` 0, and `CellStyle(bold=True) | CellStyle(bold=False)` is not bold.
  Previously a field set to its default was treated as unset and ignored.

- [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  An element with a `content_color` but no margin, border, padding or text now paints its background.
  Previously it painted nothing. An element with none of these and no `content_color` still paints nothing,
  so an undecorated container laid over other elements leaves them visible.

- A component replaced by a plain element at the same position is now unmounted:
  its effects are cancelled, and components nested under it start with fresh state.
  Previously the element inherited the component's hooks, so its effects
  (including `use_mouse` listeners) kept running.

- Effects that rerun or unmount in a render are cancelled concurrently,
  and all of them finish before any effect starts,
  so an effect's cleanup always finishes before its replacement or a sibling's setup begins.
  If several of those cleanups raise, all of their exceptions are reported together in one exception group.
  Previously a rerun effect's new task started before the old one was cancelled.

- Keyed sibling components are matched by key across renders rather than by position,
  so reordering, inserting, or removing keyed children keeps each one's state and effects.
  Unkeyed children still match the unkeyed child at the same index.

- [#125](https://github.com/JoshKarpel/counterweight/pull/125)
  Mouse wheel scroll events are now captured correctly
  (they were previously reported as mouse presses).
  The `check-input` CLI subcommand is also fixed
  (was broken by [#86](https://github.com/JoshKarpel/counterweight/pull/86)).

- `app` stops reading keys from the terminal before it returns,
  so input typed afterward reaches whatever runs next.
  Previously its key-reading thread kept running and consumed that input.

### Removed

- [#305](https://github.com/JoshKarpel/counterweight/pull/305)
  The following style types have been removed; layout is now configured directly via
  `waxy.Style` on the `Style.layout` field or through the new utility helpers:
  `Border`, `BorderEdge`, `Margin`, `Padding`, `Content`, `Span`, `Typography`,
  `Relative`, `Absolute`, `Fixed`, `Flex`, `Inset`.
  The `Style` model is now flat: border, margin, padding, typography, and positioning
  properties are top-level fields rather than nested sub-models.

- [#305](https://github.com/JoshKarpel/counterweight/pull/305)
  `counterweight.geometry.Rect` and `counterweight.geometry.Edge` have been removed.
  Use `counterweight.geometry.Region` in place of `Rect`.

- [#165](https://github.com/JoshKarpel/counterweight/pull/165),
  [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  Dropped support for Python `3.11` through `3.14`.
  Python `3.15` or later is now required.

## `0.0.9`

Released `2024-02-27`

### Fixed

- [#121](https://github.com/JoshKarpel/counterweight/pull/121)
  A change in effect reconciliation introduced in `0.0.8` caused a regression in the behavior of `use_effect`,
  where if the `setup` function `return`ed (i.e., stopped itself),
  Counterweight would crash when trying to cancel the effect.
  This now works again.

## `0.0.8`

Released `2024-02-17`

### Changed

- [#110](https://github.com/JoshKarpel/counterweight/pull/110)
  Calling a `use_state` setter with a `value` equal to the current value of the state
  no longer emits a `SetState` event, to avoid triggering unnecessary render cycles.

- [#111](https://github.com/JoshKarpel/counterweight/pull/111)
  Border healing is now more efficient, especially when there are many non-border characters in the UI.

- [#112](https://github.com/JoshKarpel/counterweight/pull/112)
  Major, backwards-incompatible changes to how Counterweight handles mouse interactions.
  The `on_mouse_down` and `on_mouse_up` event handlers have been removed;
  use the new combined `on_mouse` event handler instead, which receives all mouse events
  ([`MouseMoved`][counterweight.events.MouseMoved],
  [`MouseDown`][counterweight.events.MouseDown], and
  [`MouseUp`][counterweight.events.MouseUp]).
  The `on_hover` style attribute on elements has been removed;
  use the new
  [`use_mouse`](hooks/use_mouse.md),
  [`use_rects`](hooks/use_rects.md),
  and [`use_hovered`](hooks/use_hovered.md)
  hooks instead, and calculate the desired style in your component.
  The goal of these changes is to provide more flexibility and control over mouse interactions
  to application authors while minimizing the work that Counterweight needs to do while rendering,
  at the cost of more complex application code for simple cases like detecting hover state.

## `0.0.7`

Released `2024-02-02`

### Changed

- [#105](https://github.com/JoshKarpel/counterweight/pull/105)
  `Screenshot` and `Suspend` handlers can now be `async` functions.

## `0.0.6`

Released `2024-01-28`

### Added

- [#92](https://github.com/JoshKarpel/counterweight/pull/92)
  Added an `inset` attribute to `Absolute` that chooses which corner
  of the parent's context box to use as the origin for the absolute positioning.

- [#98](https://github.com/JoshKarpel/counterweight/pull/98)
  Added a `z` attribute to `Flex` that controls the stacking order of elements.

### Changed

- [#101](https://github.com/JoshKarpel/counterweight/pull/101)
  The `initial_value` of [`use_ref`][counterweight.hooks.use_ref] may now be a `Callable[[], T]` instead of just a `T`.

### Removed

- [#96](https://github.com/JoshKarpel/counterweight/pull/96)
  `Chunk`s can no longer be created with `CellPaint`s directly.

## `0.0.5`

Released `2024-01-06`

### Added

- [#86](https://github.com/JoshKarpel/counterweight/pull/86)
  Added a `Suspend` control which suspends the Counterweight application while a user-supplied callback function runs.
  Counterweight will stop controlling the terminal while the callback runs, and will resume when the callback returns.
  This can be used to run a subprocess that also wants control of the terminal (e.g., a text editor).

- [#88](https://github.com/JoshKarpel/counterweight/pull/88)
  [#90](https://github.com/JoshKarpel/counterweight/pull/90)
  Implemented `Absolute` and `Fixed`
  positioning, which allow for precise placement of elements outside the normal layout flow.

## `0.0.4`

Released `2023-12-31`

### Fixed

- [#83](https://github.com/JoshKarpel/counterweight/pull/83)
  Fixed virtual terminal escape code parsing for mouse tracking when the moues coordinates are large (>94 or so).
  Mouse tracking should now work for any terminal size.
  Various `Key` members that aren't currently parseable have been removed to avoid confusion.

## `0.0.3`

Released `2023-12-30`

### Changed

- [#71](https://github.com/JoshKarpel/counterweight/pull/71)
  Controls are now a union over different `@dataclass`es (instead of an `Enum`) to allow for more flexibility.
  The `Screenshot` control now takes a callback function which will be called with the SVG screenshot as an XML tree.

- [#81](https://github.com/JoshKarpel/counterweight/pull/81)
  The minimum Python version has been raised to `3.11.2` due to a [bug in CPython `3.11.1`](https://github.com/python/cpython/issues/100098)

## `0.0.2`

Released `2023-12-26`

### Added

- [#65](https://github.com/JoshKarpel/counterweight/pull/65)
  Added ability to take an SVG "screenshot" by returning `Control.Screenshot` from an event handler.
  The screenshot will be saved to the current working directory as `screenshot.svg`; more options will be added in the future.

- [#66](https://github.com/JoshKarpel/counterweight/pull/66)
  Added "border healing": when border elements for certain border types are adjacent to each other and appear as if they
  should "join up", but don't because they belong to different elements, they will now be joined up.

### Changed

- Various namespaces moved around to make more sense (especially in documentation)
  and separate concerns better as part of [#68](https://github.com/JoshKarpel/counterweight/pull/68).

## `0.0.1`

Released `2023-12-19`
