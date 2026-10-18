# Plan: Examples in the Library

Artifact: https://claude.ai/code/artifact/18c9dff7-8a23-4b8f-a116-e71371d43ea7

This plan moves every example, the complete apps in `examples/` and the docs snippets in `docs/examples/`,
into the library as `counterweight.examples`,
sorts them into two kinds with a real difference between them (a few apps and many snippets),
tests them like the rest of the library,
and adds a `counterweight examples` command that lists, runs, shows and copies them,
with a gallery app that browses them.
The docs keep pulling snippets out of the same modules by section, and keep their screenshots and recordings.
It doesn't cover editing an example live in the gallery, or examples in the README.

## The question

How do users run and copy the examples without cloning the repository,
and how do the examples stay correct as the library changes,
without giving up the docs' snippets, screenshots and recordings?

Today the examples live in two trees that ship in no wheel:

| Tree | What's there | How it runs | What checks it |
| --- | --- | --- | --- |
| `examples/` | 17 complete apps (chat, wordle, multiplexer, ...) | `uv run python -m examples.<name>` from a clone | mypy |
| `docs/examples/` | about 65 modules of docs snippets, each declaring `SCREENSHOTS` and maybe `CASTS` | `uv run python -m docs.examples.<name> [root]` from a clone | mypy, and rendering them in pre-commit |

Neither counts toward coverage, the apps are never run by anything,
and a user who installed counterweight from PyPI has none of them.

## Ranked goals

1. A user who installed counterweight can run, read and copy any example.
2. Examples can't silently break: the test suite runs them, and coverage holds them to the same bar as the library.
3. The docs keep showing code from the examples by section, with the screenshots and recordings they declare.
4. The examples are fewer and more distinct: each one is either a small app or a snippet of one idea.

The cost, accepted:
the wheel carries the examples' modules (Python source only, no assets);
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
| Runs | One root, which may take command-line arguments | One or more roots, which take no arguments |
| Docs | The home page's showcase, the gallery's first group, linked from feature pages | Embedded in one section of one page |
| Tests | Tests of its own behavior, and its demo run to the end | Its screenshots compared with the committed ones, and its recordings run to the end |
| Recording | A demo that tells a story | Screenshots, and a recording where motion is the point |
| Copying | A starting point for an app | A pattern to paste into one |

### The apps

About six, each standing for a kind of app people build with counterweight:

| App | Kind of app | What it composes |
| --- | --- | --- |
| `todo` | The quick start | `use_state`, a text input, focus, clicks |
| `chat` | An agent or chat transcript | A text area, Markdown streaming in, following the end, `memo` |
| `markdown_viewer` | A file browser | A tree, scroll areas, Markdown, keys and mouse |
| `multiplexer` | A terminal tool | Embedded terminals, prefix keys, focus |
| `wordle` | A game | A grid, keys, state, colors |
| `slides` | A presentation | Markdown, one-shot commands, suspending to an editor |

The rest of `examples/` becomes snippets or goes:

| Today | Becomes |
| --- | --- |
| `table` | A snippet, the sortable table the ecosystem page links to |
| `stopwatch` | Covered by the `use_clock` lap timer; dropped |
| `mouse`, `scrolling`, `text_wrap`, `borders` | Covered by the input, scrolling, text-wrapping and border snippets; dropped |
| `markdown_gallery` | Its sample documents move into `markdown_viewer`'s demo; dropped |
| `suspend` | Covered by the programs snippets; dropped |
| `canvas` | A snippet once it's deterministic (seeded, timed by `use_clock` rather than `sleep`) |
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
  and could be two roots of one module.

Where a page needs another state of an existing snippet, it adds a screenshot of that snippet after more steps,
rather than a new module.

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
    """`root` at `dimensions` as `steps` drive it, which the docs save as a recording and `run --demo` plays."""

    name: str
    root: Component
    dimensions: tuple[int, int]
    steps: Sequence[AutopilotStep]
```

A module declares `STILLS` and, if it has any, `DEMOS`, in place of `SCREENSHOTS` and `CASTS`.
`name` is the asset name the docs write (`docs/assets/<name>.svg`, `.txt`, `.cast`),
which keeps every page's links working through the move.
The paths themselves stay in the docs tooling.

`paced`, which spaces steps out as a person types, becomes public as `counterweight.autopilot.paced`,
since anyone recording a demo of their own app wants it.

## The catalog

The catalog is derived from the modules, never kept by hand:

- **What's an example:** every module in `counterweight.examples.apps` and `counterweight.examples.snippets`.
- **Its title and description:** the first line and the rest of the module docstring.
- **Its roots:** for a snippet, the root functions its scenes use (each scene's `root` is a `Component`, which names its function),
  so a root without a scene can't exist and every root the CLI runs is one the tests render;
  for an app, its `root`.
- **Its name:** the module's name with hyphens (`layout-splitting`), and a root after a colon (`layout-splitting:fill`).
  A module with one root needs no colon.

Listing imports every example module.
Measure how long `counterweight examples list` takes; if importing them is slow,
read titles and descriptions from the source with `ast` and import only the one being run.

## The CLI

`counterweight examples` is a group in `cli.py` (built with `without-cli`):

| Command | Does |
| --- | --- |
| `counterweight examples` | Opens the gallery |
| `counterweight examples list` | Prints each example's name and title, apps first, as text a script can read |
| `counterweight examples run <name> [args]` | Runs the example; an app gets `args` |
| `counterweight examples run <name> --demo` | Plays one of its demos in the terminal, at its own pace, then leaves the app running |
| `counterweight examples show <name>` | Prints its source, highlighted, through `$PAGER` (`less -R` without one) when standard output is a terminal, and plain otherwise |
| `counterweight examples show <name> -o <path>` | Writes the plain source to a file |
| `counterweight examples copy <name> [path]` | Writes a standalone file that runs the example, for a user to start from |

`show` and `copy` strip the `# --8<--` section markers.
`copy` adds the imports a snippet's section leaves out and an `if __name__ == "__main__":` that runs its root,
so the copied file runs as it is.

Example modules have no `__main__` blocks: the CLI runs them, and a block the CLI never runs would be the one uncovered line in every module.
`show` highlights with `counterweight.highlighting`, painted headless into ANSI text, so the CLI uses the library's own code view.

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
 Enter: use it   d: play the demo   s: source   c: copy   Ctrl+B: back to the list
```

- The list groups apps first, then snippets by their docs section.
- The preview runs the selected example; Enter focuses it, so keys and the mouse reach the example,
  and a prefix key (Ctrl+B, as the multiplexer uses) brings focus back, since an example may claim every other key.
- `d` plays a demo in the preview, `s` toggles the source, and `c` copies the example as `copy` does.

### How the preview runs an example

There are two ways, and they trade isolation against speed:

| | In process: render the root as a component in the preview | In a subprocess: `counterweight examples run <name>` in an embedded terminal |
| --- | --- | --- |
| Starting | Instant | A new interpreter, a few hundred milliseconds (to measure) |
| Isolation | None: an example's `Quit` quits the gallery, its root's handlers and unclaimed keys mix with the gallery's, its focus joins the gallery's focus order | Complete: it's its own app |
| Demos | Need an autopilot for one subtree, which doesn't exist | `run --demo`, as on the command line |
| Examples that embed terminals or suspend | Suspending would suspend the gallery | Work as they do alone |

The subprocess wins: isolation is what lets every example run unchanged, and the embedded terminal already exists.
What it costs is the start-up delay on each selection and a process per preview,
which the gallery bounds by running only the selected example and hanging up the last one.

## Tests

- **Every still:** render it headless at the docs' frozen time with `check_purity=True`,
  and compare its text with the committed `docs/assets/<name>.txt`.
  A rendering change then fails a test instead of only changing an asset in pre-commit,
  and the message says to run `docs/generate_screenshots.py`.
- **Every demo:** run it to the end, which runs the handlers the stills don't reach.
- **Apps:** tests of their own logic where the scenes leave branches uncovered.
- **The catalog and the CLI:** names, titles, roots, `list` output, `show` and `copy` output (that a copied file runs),
  `run` exiting cleanly under an autopilot.
- **The gallery:** driven by its own demo and stills, as any example is.

Mutation testing skips `counterweight.examples`: a mutant in an example tests nothing about the library.
Check that mutmut can exclude a subpackage before relying on it;
if it can't, find another way before the examples join `src`.

## Prerequisites

Demos have to run the same way every time, and the docs pass turned up three things in the way:

- **An autopilot starves effects.** The render loop doesn't yield to the event loop while autopilot steps keep coming
  (`Queue.put` and `get` on a non-empty queue don't suspend), so effects started in `handle_effects` don't run until a `Wait` or `WaitFor`.
  `use_mouse` and `use_hovered` subscribe in a mount effect, so they miss autopilot mouse events,
  and an effect's work only progresses while the autopilot waits in real time, which no recording can do the same way twice.
  The docs examples work around it with a one-millisecond `Wait` before the first move,
  and the `use_effect` and `use_controls` pages show screenshots where a recording would serve better.
  Fix it so the loop lets started effects run between steps, and a demo needs no real-time wait.
- **Follow-up renders lag a step.** The render that `use_rects` and `use_scroll` queue when what they read moves
  is handled together with the next autopilot step, so a recording shows the corrected frame one pause late.
  The docs examples add an `AdvanceClock(by=timedelta())` after each input to flush it.
  Fix it so an autopilot step is followed by the renders it causes, as a person's key press is.
- **Examples with real processes.** The programs snippets run `sh` as a stand-in editor while rendering.
  That's fine in tests on Linux and macOS, but keep such scenes few, since every test run starts them.

## Steps

Each step leaves the docs building, the tests passing and coverage at 100%.

1. **Scenes.** Add `Still`, `Demo` and public `paced`, and switch `docs/examples` to them (`STILLS`, `DEMOS`). No moves yet.
2. **Move.** Move `docs/examples/*.py` to `counterweight/examples/snippets/` and `examples/*.py` to `counterweight/examples/apps/`,
   drop the `__main__` blocks, and update the imports, the mkdocs examples hook, the screenshot generator, the pre-commit hook's `files`, and `CLAUDE.md`.
   Coverage omits `counterweight/examples` for this step only.
3. **Tests.** Add the still and demo tests and the apps' tests, and remove the omission.
4. **Two kinds.** Fold and drop apps as in [The apps](#the-apps), consolidate snippets as in [The snippets](#the-snippets),
   and update the pages that show them and the home page's showcase.
5. **CLI.** Add the catalog and `counterweight examples list`, `run`, `show` and `copy`.
6. **Gallery.** Add the gallery, and make it what `counterweight examples` opens.
7. **Docs.** A page on the examples and the gallery, the home page pointing to `counterweight examples`,
   and a changelog entry.

## Open questions

- **What does a bare `counterweight examples` do?** The gallery is the front door for a person, `list` is for scripts.
  Opening the gallery is the recommendation; the alternative is to list, and make `gallery` a subcommand.
- **Apps that take arguments.** `markdown_viewer` takes a directory.
  Should an app declare its arguments with `without-cli` options in its module, so `run --help` describes them,
  or take a plain list of strings?
- **Snippet names.** Module names with hyphens and a root after a colon is the proposal;
  the docs sections don't line up with roots, so names can't come from the sections.
- **Asset names.** Keeping each scene's `name` as its asset name avoids renaming every asset.
  Deriving it from the module and scene names would be tidier, at the cost of one large rename.
