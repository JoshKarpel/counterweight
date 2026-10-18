# Plan: Examples in the Library

Artifact: https://claude.ai/code/artifact/18c9dff7-8a23-4b8f-a116-e71371d43ea7

This plan moves every example, the complete apps in `examples/` and the docs snippets in `docs/examples/`,
into the library as `counterweight.examples`,
sorts them into two kinds with a real difference between them (a few apps and many snippets),
tests them like the rest of the library,
and adds a `counterweight examples` command that lists, runs, shows and copies them,
with a gallery app that browses them and runs each one in place.
The docs keep pulling snippets out of the same modules by section, and keep their screenshots and recordings.
It doesn't cover editing an example live in the gallery, examples in the README,
or playing a recorded demo outside the docs (see [Future work](#future-work)).

## The question

How do users run and copy the examples without cloning the repository,
and how do the examples stay correct as the library changes,
without giving up the docs' snippets, screenshots and recordings?

Today the examples live in two trees that ship in no wheel:

| Tree | What's there | How it runs | What checks it |
| --- | --- | --- | --- |
| `examples/` | 16 complete apps (chat, wordle, multiplexer, ...) | `uv run python -m examples.<name>` from a clone | mypy |
| `docs/examples/` | about 65 modules of docs snippets, each declaring `SCREENSHOTS` and maybe `CASTS` | `uv run python -m docs.examples.<name> [root]` from a clone | mypy, and rendering them in pre-commit |

Neither counts toward coverage, the apps are never run by anything,
and a user who installed counterweight from PyPI has none of them.

## Ranked goals

1. A user who installed counterweight can run, read and copy any example.
2. Examples can't silently break: the test suite runs them, and coverage holds them to the same bar as the library.
3. The docs keep showing code from the examples by section, with the screenshots and recordings they declare.
4. The examples are fewer and more distinct: each one is either a small app or a snippet of one idea.

The cost, accepted:
the wheel carries the examples' modules and `markdown_viewer`'s sample documents;
examples count toward the 100% coverage gate, so their branches need tests;
example names become a semi-stable interface, since the CLI exposes them;
and `counterweight.examples` looks importable while being no part of the public API.

## How the web does it

- **[Storybook](https://storybook.js.org/docs/writing-stories)** is the closest match.
  A story is a component with its arguments, declared in a file beside the component,
  and one declaration serves three uses: the docs page, a visual snapshot test, and an interaction test,
  whose [play function](https://storybook.js.org/docs/writing-stories/play-function) drives the component the way a user would.
  Story titles come from the file's path, not a hand-kept list.
  Counterweight's `ScreenshotSpec` and `CastSpec` are stories, and a cast's steps are a play function.
  Storybook renders each story in an iframe, isolated from the browser around it;
  the gallery mounts examples in its own tree instead (see [The gallery](#the-gallery)).
- **React's docs** embed [Sandpack](https://sandpack.codesandbox.io/) sandboxes,
  so every example is runnable and editable where it's read.
  A terminal can't embed one in a web page, but the gallery can put the code beside the running example.
- **Templates**, such as `npm create vite`, copy a working starting point into the user's project.
  `counterweight examples copy` does that for one example.

How the other terminal frameworks ship examples:

- **Rich** and **Textual** ship a demo in the package (`python -m rich`, `python -m textual`),
  but Textual's docs examples live in the repository only.
- **Bubble Tea** and **Ratatui** keep examples in the repository, run with `go run` and `cargo run --example`.

Counterweight goes further than either: every example ships, and the docs' screenshots become tests.

## Two kinds of example

The difference is what an example is for, and it shows in size, entry point, tests and where it appears:

| | App | Snippet |
| --- | --- | --- |
| Shows | Many features composed into something useful | One idea, the one its docs section is about |
| Size | 150 to 450 lines, several components | Up to about 60 lines in the section a page shows |
| Runs | One root | One or more roots |
| Docs | The home page's showcase, the gallery's first group, linked from feature pages | Embedded in one section of one page |
| Tests | Tests of its own behavior, and its scenes | Its scenes compared with the committed screenshots and recordings |
| Recording | A recording that tells a story | Screenshots, and a recording where motion is the point |
| Copying | A starting point for an app | A pattern to paste into one |

No root takes command-line arguments.
A root may take keyword arguments with defaults, which its scenes use to show it in a known state
(a fixed directory, a fixed command); the CLI and the gallery call it with none.

### The apps

About six, each standing for a kind of app people build with counterweight:

| App | Kind of app | What it composes |
| --- | --- | --- |
| `todo` | The quick start | `use_state`, a text input, focus, clicks |
| `chat` | An agent or chat transcript | A text area, Markdown streaming in, following the end, `memo` |
| `markdown_viewer` | A file browser | A tree, scroll areas, Markdown, keys and mouse |
| `multiplexer` | A terminal tool | Embedded terminals, direct hotkeys, focus |
| `wordle` | A game | A grid, keys, state, colors |
| `slides` | A presentation | Markdown, one-shot commands, suspending to an editor |

`todo` is the quick start's `todo_list` (`docs/examples/home_quick_start.py`), promoted from a snippet;
the home page keeps embedding its section.

Three apps change shape:

- **`markdown_viewer`** drops its directory argument, and its tree's root is the working directory.
  Its root takes that directory, the working directory by default, and its scenes use sample documents shipped beside it
  (the ones `markdown_gallery` shows today; the wheel already ships non-Python files in the package, such as `py.typed`).
- **`multiplexer`** uses direct hotkeys, as zellij does, rather than tmux's prefix:
  Alt+N opens a pane, Alt+Left and Alt+Right move focus, and Alt+X closes the focused pane,
  with a bar along the bottom that always shows them.
  Ctrl+C and Ctrl+Z go to the focused shell like every other key,
  and the multiplexer quits when its last pane closes, as tmux does when its last shell exits.
  Its root takes the command each pane runs, `$SHELL` by default;
  its scenes run a plain `sh` with a fixed prompt and environment, so they come out the same for everyone.
  Alt keys need Option set to send Meta in macOS terminals, as zellij's do, and the module docstring says so.
- **`slides`** runs commands whose output is the same on every machine and on both platforms CI runs (Linux and macOS).
  On mount it makes a scratch directory of a few fixed files and runs its commands there:
  `ls -F` lists it (`ls -la` would show owners, times, block counts and directory sizes that differ by machine and filesystem),
  `cat` shows a file, `printf` prints colored text in place of `uname -a`,
  the streaming `seq` loop stays,
  and `cat` of a missing file fails in place of `ls /no/such/directory`, whose message differs between GNU and BSD `ls`.
  The still tests run on both platforms, so they check that the output matches.

The rest of `examples/` becomes snippets or goes:

| Today | Becomes |
| --- | --- |
| `table` | A snippet, the sortable table the ecosystem page links to |
| `stopwatch` | Covered by the `use_clock` lap timer; dropped |
| `mouse`, `scrolling`, `text_wrap`, `borders` | Covered by the input, scrolling, text-wrapping and border snippets; dropped |
| `markdown_gallery` | Its sample documents become `markdown_viewer`'s; dropped |
| `suspend` | Covered by the programs snippets; dropped |
| `canvas` | Covered by the canvas snippet (pictures, painters, drawing with the mouse) and the `use_clock` snippets (animation); dropped |
| `chess` | A grid-layout snippet, or dropped |
| `end_to_end` | Dropped |

### The snippets

The docs modules stay grouped by topic, a module per page or per section of a long page,
since a page that shows eleven ways to split space reads better from one module than eleven.
Consolidating them is a review against two rules:
one idea per snippet, and no two snippets showing the same idea.
Known overlaps to settle:

- Three counters: `use_state_counter`, `input_overview` and the quick start.
- `use_clock_lap_timer` and `use_clock_status_bar` against the old stopwatch app.
- `performance_state_in_root` and `performance_state_moved_down`, which are one idea in two states
  and become two roots of one module.

Where a page needs another state of an existing snippet, it adds a screenshot of that snippet after more steps,
rather than a new module.

A snippet imports from the library and its dependencies, never from another example,
so `copy` can hand it over as one file.
Three do today, and each pair settles into one module or stops sharing:

- `performance_state_moved_down` imports from `performance_state_in_root`: one module, as above.
- `autopilot_search` imports `search` from `text_input`: it keeps its own copy of the small component.
- `terminals_multiplexer` imports the replay helpers from `emulator_replay`: one module.

The canvas snippet's image section stops importing `codegen.generate_logo`,
which builds the logo from font files at import with fonttools, a development-only dependency.
It shows Pillow's Mandelbrot set instead,
`ImageOps.colorize(Image.effect_mandelbrot(...))`, a real Pillow image with no file behind it,
detailed enough that the fit modes look different.

## Layout in the package

```text
src/counterweight/examples/
├── __init__.py        # says the package isn't public API, and what belongs in each subpackage
├── catalog.py         # finds the examples and their roots, scenes, titles and descriptions
├── scenes.py          # Still, Demo
├── gallery.py         # the gallery app
├── apps/
│   ├── todo.py
│   ├── chat.py
│   ├── markdown_viewer.py
│   ├── markdown_samples/
│   └── ...
└── snippets/
    ├── layout_splitting.py
    ├── use_mouse.py
    └── ...
```

`docs/examples/screenshot_spec.py` becomes `counterweight.examples.scenes`,
and `docs/examples/generate_screenshots.py` stays docs tooling, as `docs/generate_screenshots.py`,
reading everything it renders from the catalog.

## Scenes

A scene is what a screenshot or a recording shows, as a value with nothing about files in it:

```python
@dataclass(frozen=True, slots=True)
class Still:
    """What `root` shows at `dimensions` after `steps`, which the docs save as a screenshot."""

    name: str
    root: Component
    dimensions: tuple[int, int]
    steps: Sequence[AutopilotStep] = ()


@dataclass(frozen=True, slots=True)
class Demo:
    """`root` at `dimensions` as `steps` drive it, which the docs save as a recording."""

    name: str
    root: Component
    dimensions: tuple[int, int]
    steps: Sequence[AutopilotStep]
```

A module declares `STILLS` and, if it has any, `DEMOS`, in place of `SCREENSHOTS` and `CASTS`.
`name` is the asset name the docs write (`docs/assets/<name>.svg`, `.txt`, `.cast`),
which keeps every asset's name, and every page's links, through the move.
The paths themselves stay in the docs tooling.

A scene is one autopilot run written down as a value.
The docs tooling turns a `Still` into
`app(root, headless=True, dimensions=..., autopilot=[*steps, Screenshot(...), Quit()], check_purity=True, clock=FrozenClock(...))`,
adding the docs' conventions: a frozen start time, the purity check, and a screenshot before quitting.
Being values is what lets the docs tooling, the tests and the catalog enumerate them without running them.
They stay out of the public API, because a user can already do all of this with `app`, an autopilot,
`Screenshot` and `FrozenClock`.

`paced`, which spaces steps out as a person types, becomes public as `counterweight.autopilot.paced`,
since anyone recording their own app wants it.

## The catalog

The catalog is derived from the modules, never kept by hand:

- **What's an example:** every module in `counterweight.examples.apps` and `counterweight.examples.snippets`.
- **Its title and description:** the first line and the rest of the module docstring.
- **Its roots:** for a snippet, the root functions defined in the module that its scenes use
  (each scene's `root` is a `Component`, which names its function),
  so a root without a scene can't exist and every root the CLI runs is one the tests render;
  for an app, its `root`.
- **Its name:** the module's name with hyphens (`layout-splitting`), and a root after a colon (`layout-splitting:fill`).
  A module with one root needs no colon.

Listing imports every example module, which takes about a second, most of it importing `counterweight.app` itself.
That's also the start-up time of every counterweight app, so the fix belongs in the library:
it uses Python 3.15's explicit `lazy import` for the modules an app may never touch
(profile which before choosing).
The global lazy-imports mode isn't an option, since it breaks fontTools.

## The CLI

`counterweight examples` is a group in `cli.py` (built with `without-cli`):

| Command | Does |
| --- | --- |
| `counterweight examples` | Opens the gallery |
| `counterweight examples list` | Prints each example's name and title, apps first, as text a script can read |
| `counterweight examples run <name>` | Runs the example |
| `counterweight examples show <name>` | Prints its source, highlighted, through `$PAGER` (`less -R` without one) when standard output is a terminal, and plain otherwise |
| `counterweight examples show <name> -o <path>` | Writes the plain source to a file |
| `counterweight examples copy <name> [path]` | Writes a standalone file that runs the example, for a user to start from |

Example modules keep their `if __name__ == "__main__":` blocks,
so each one runs with `python -m counterweight.examples.snippets.<module>`,
and coverage ignores them through `exclude_also`, as it does `if TYPE_CHECKING:`.
Each module's scenes come last, after a `# --8<-- [start:scenes]` marker, with the imports only they use.
`show` strips the `# --8<--` markers;
`copy` strips them and the scenes section, so the copied file is the module as it runs, and runs as it is.

`show` highlights with `counterweight.highlighting`, painted headless into ANSI text (`Frame.text(ansi=True)`),
so the CLI uses the library's own code view.

## The gallery

The gallery is a counterweight app, and the largest example of one:

```text
┌ Examples ─────────────┐┌ chat ────────────────────────────────────────────┐
│ Apps                  ││ A chat with a canned bot, whose replies are      │
│ ▸ chat                ││ Markdown that streams in a word at a time.       │
│   markdown-viewer     │├──────────────────────────────────────────────────┤
│   multiplexer         ││ ┌──────────────────────────────────────────────┐ │
│   ...                 ││ │ (the example, running)                       │ │
│ Layout                ││ │                                              │ │
│   layout-splitting    ││ └──────────────────────────────────────────────┘ │
│   ...                 │├ Source ──────────────────────────────────────────┤
│ Input                 ││ @component                                       │
│   ...                 ││ def root() -> Div:                               │
└───────────────────────┘└──────────────────────────────────────────────────┘
 Enter: use it   s: source   c: copy   Ctrl+]: back to the list
```

- The list groups apps first, then snippets by their docs section.
- The preview mounts the selected example's root in the gallery's own tree.
  Enter moves focus into it (`FocusNext` within the preview's `Subtree`), so keys and the mouse reach the example,
  and Ctrl+] brings focus back to the list.
- `s` toggles the source, and `c` copies the example as `copy` does.

### Mounting examples in place

Mounting starts an example instantly, and keeps the gallery's stills as deterministic as any example's.
What it costs is isolation, which the examples make up for by convention:

- **Focus comes back on Ctrl+].**
  A key goes to the focused element and bubbles up until a handler claims it, so the gallery's handler, above the preview,
  sees Ctrl+] as long as nothing in the example claims it.
  The library's widgets don't (its text inputs do claim Ctrl+B, to move back a character, which rules that key out),
  and Ctrl+] is the traditional key for leaving an embedded session, as in `telnet` and `virsh console`.
  An embedded terminal claims every key, so the examples that focus one (`multiplexer`, the terminals snippets)
  put a handler in front of it that lets Ctrl+] through, as they already do for their own keys.
  A test mounts every example in the gallery, tabs to each focusable element, presses Ctrl+],
  and checks that focus is back on the list, so the convention can't silently break.
- **Tab can leave the example.** Its focusable elements join the gallery's focus order, so Tab past its last one reaches the list.
- **Suspending suspends the gallery**, which comes back when the program ends, as the example would alone.
- **Ctrl+C quits the gallery**, since it's the app's default for a key nothing claims.

#### Quitting

An example that quits on its own would quit the gallery,
so examples quit on Ctrl+C, the app's default, wherever they can.
These return `Quit` today:

| Example | Quits on | Becomes |
| --- | --- | --- |
| `wordle` | `q` | Ctrl+C |
| `input_overview` snippet | `q` | Ctrl+C |
| `input_handlers` snippet | `q` | Ctrl+C |
| `input_controls` snippet | Ctrl+Q | Ctrl+C |
| `multiplexer` | Ctrl+Q, and closing its last pane | Closing its last pane |
| `terminals` snippet | Ctrl+Q | Ctrl+Q |

`text_wrap` and `scrolling` quit too, and are dropped.
The pages that mention the dropped keys change with them:
the input overview names another control in place of the counter's `q`,
and the controls page drops Ctrl+Q from its list.

Two can't quit on Ctrl+C, because their focused terminal sends it to the program.
The `terminals` snippet keeps Ctrl+Q, since claiming a key for that reason is what its section teaches,
and the multiplexer quits when its last pane closes.
In the gallery, either one quits the gallery, which is accepted
rather than giving their roots an argument that only the gallery would pass.

## Tests

- **Every still:** render it headless at the docs' frozen time with `check_purity=True`,
  and compare its SVG and its text with the committed `docs/assets/<name>.svg` and `.txt`,
  so a change only to colors or styles fails too.
  A rendering change then fails a test instead of only changing an asset in pre-commit,
  and the message says to run `docs/generate_screenshots.py`.
- **Every demo:** run it to the end, which runs the handlers the stills don't reach.
- **Apps:** tests of their own logic where the scenes leave branches uncovered.
- **The catalog and the CLI:** names, titles, roots, `list` output, `show` and `copy` output (that a copied file runs),
  `run` exiting cleanly under an autopilot.
- **The gallery:** its own stills and demos, as any example has,
  and the Ctrl+] test in [Mounting examples in place](#mounting-examples-in-place).

Mutation testing skips `counterweight.examples`, since a mutant in an example tests nothing about the library:
mutmut's `do_not_mutate` takes globs matched against each file's path,
so `do_not_mutate = ["src/counterweight/examples/*"]` in `[tool.mutmut]` does it.

## Prerequisites

Scenes have to come out the same way every time, and the docs pass turned up three things in the way:

- **An autopilot starves effects.** The render loop doesn't yield to the event loop while autopilot steps keep coming
  (`Queue.put` and `get` on a non-empty queue don't suspend), so effects started in `handle_effects` don't run until a `Wait` or `WaitFor`.
  `use_mouse` and `use_hovered` subscribe in a mount effect, so they miss autopilot mouse events,
  and an effect's work only progresses while the autopilot waits in real time, which no recording can do the same way twice.
  The docs examples work around it with a one-millisecond `Wait` before the first move
  (`styles_merging`, `use_hovered`, `use_mouse`),
  and the `use_effect` and `use_controls` pages show screenshots where a recording would serve better.
  Fix it so the loop lets started effects run between steps, and a scene needs no real-time wait.
- **Follow-up renders lag a step.** The render that `use_rects` and `use_scroll` queue when what they read moves
  is handled together with the next autopilot step, so a recording shows the corrected frame one pause late.
  The docs examples add an `AdvanceClock(by=timedelta())` after each input to flush it
  (`use_rects_path_label`, `use_scroll_position`).
  Fix it so an autopilot step is followed by the renders it causes, as a person's key press is.
- **Programs need a working directory.** `run_program` takes a `cwd`, but `run_pty`, `use_pty`, `use_command` and `use_terminal` don't,
  so `slides` can't run its commands in its scratch directory without the path showing in every command line.
  Add `cwd: Path | None = None` to each, beside `run_program`'s.

Scenes that start real processes (the programs snippets' stand-in editor, `slides`, the multiplexer's `sh`) run in every test run,
which is fine on Linux and macOS; keep them few.

## Steps

Each step leaves the docs building, the tests passing and coverage at 100%.

0. **Prerequisites.** Fix the two autopilot problems and add `cwd`, as in [Prerequisites](#prerequisites),
   and take the workarounds out of the docs examples.
1. **Scenes.** Add `Still`, `Demo` and public `paced`, and switch `docs/examples` to them (`STILLS`, `DEMOS`). No moves yet.
2. **Two kinds.** In place, fold and drop apps as in [The apps](#the-apps),
   reshape `markdown_viewer`, `multiplexer` and `slides`, move quitting to Ctrl+C as in [Quitting](#quitting),
   consolidate snippets as in [The snippets](#the-snippets), replace the canvas snippet's logo,
   and update the pages that show them and the home page's showcase.
3. **Move.** Move `docs/examples/*.py` to `counterweight/examples/snippets/` and `examples/*.py` to `counterweight/examples/apps/`,
   move each module's scenes after its scenes marker, and update every reference to the old paths:
   the imports, the tests that import `docs.examples` (`test_prefix_keys_guide.py`, `test_performance_guide.py`),
   the mkdocs examples, casts and screenshot tabs hooks, the screenshot generator, the pre-commit hook's `files`,
   the `justfile`, `CLAUDE.md`,
   and the links to `examples/` in `docs/index.md`, `docs/ecosystem.md` and the unreleased `0.1.0` changelog entries.
   Coverage omits `counterweight/examples` for this step only.
4. **Tests.** Add the still and demo tests and the apps' tests, remove the omission, and set mutmut's `do_not_mutate`.
5. **CLI.** Add the catalog and `counterweight examples list`, `run`, `show` and `copy`,
   and make the library's heavy imports lazy.
6. **Gallery.** Add the gallery, and make it what `counterweight examples` opens.
7. **Docs.** A page on the examples and the gallery, the home page pointing to `counterweight examples`,
   and a changelog entry.

## Open questions

- **Snippet names.** Module names with hyphens and a root after a colon is the proposal;
  the docs sections don't line up with roots, so names can't come from the sections.

## Future work

- **Playing a demo outside the docs**, as `counterweight examples run <name> --demo` or a key in the gallery.
  A recording's `AdvanceClock` steps move the clock at once rather than waiting,
  so playing one in a live terminal would fire every step back to back
  and leave any `use_clock` component showing a time the demo's length in the future.
  Live playback needs each `AdvanceClock` turned into a real wait that doesn't move the clock.
