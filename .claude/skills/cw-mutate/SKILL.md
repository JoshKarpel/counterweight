---
name: cw-mutate
description: Mutation testing workflow for the counterweight project with mutmut. Use when running `just mutate`, triaging or killing surviving mutants, judging whether a counterweight mutant is equivalent, or checking how well the tests pin the shadow tree, hooks, and equivalence logic. Holds the project's known equivalent mutants and its mutmut traps; load it alongside the general `mutation-testing-python` skill.
---

# Counterweight Mutation Testing

mutmut mutates all of `src/counterweight` (configured under `[tool.mutmut]` in `pyproject.toml`).
The state modules, `shadow`, `hooks`, `equivalence`, `components`, and `app.handle_effects`,
have no survivors beyond the equivalents listed below.
The other modules haven't been triaged yet.

## Run it

```bash
just mutate                                   # every mutant without a cached verdict
just mutate 'counterweight.shadow.*'          # re-run only these mutants, cached or not
uv run mutmut results                         # what survived
uv run mutmut show <mutant>                   # one mutant's diff
```

A full cold run takes about 25 minutes on 2 CPUs, most of it in `app.render_loop`,
whose mutants each re-run every app-level test.
When working on the state modules, pass their globs to skip the rest.

Start from `rm -rf mutants` after editing a source file or a test that already existed,
and after any run that died partway: the cache keeps verdicts and the test map from before,
and a run that crashed can leave mutants marked "no tests" that never ran.

## Traps specific to this project

- **Runaway memory.** A mutant can turn a loop that must advance into one that appends forever
  (`layout._wrap_pretty`'s line reconstruction, when its DP table stays empty), at hundreds of megabytes a second.
  `tests/conftest.py` caps each mutmut worker's address space on Linux so such a mutant raises
  `MemoryError` and counts as killed. Without that cap, two of them exhaust a small VM's memory before
  mutmut's timeout fires, and a VM without swap hangs.
- **Decorators run before any mutant does.** mutmut imports the test modules in its parent process,
  so a module-level `@component` runs the unmutated `component`.
  A test that pins what a decorator builds has to apply it inside the test body.
- **Autopilot never yields to effects.** `app`'s autopilot loop doesn't await anything that suspends,
  so an effect started by a render hasn't run when the next autopilot event is handled:
  `use_mouse` hasn't subscribed when the first `MouseMoved` arrives, and that event is lost.
  Test hooks that need a running effect with `tests.rendering.render`, which yields once after starting effects.
- `tests/test_mkdocs_utility_tables.py` is skipped under mutmut: it lists the utilities module's public names,
  and mutmut adds its own.

## Known equivalent mutants

Each is equivalent for the reason given; recheck the reason, not just the shape, when a new survivor resembles one.

- **Diagnostic prose.** `XX` wraps and case changes of the fixed sentences in `InconsistentHookExecution`
  (`update_node`), `ImpureComponent` (`check_is_pure`), and `StaleMemo` (`Hooks.use_memo`).
  Tests pin what each message names (the component, the hook types, the key), not its wording.
- **`check_is_pure`'s `zip(..., strict=True)`** dropped or `False`/`None`.
  Two nodes' children are zipped only after their elements matched, and a node's children come from its element,
  so the lengths are always equal.
- **`ShadowNode.detached`'s `element=None`, and `Hooks.detached`'s `clocks` (`None` or dropped) and
  `mount_status` (`is_mounted=None`).** A detached tree is only re-rendered by `check_is_pure`,
  where every node is in `paths` and `dirty_nodes`: an element node is rebuilt from `next` without reading its
  previous element, a node's `clocks` are read only by `ShadowTree` and `is_dirty`, which never see the copy,
  and its `mount_status` is read only by a `use_state` hook created on the copy,
  which a re-run can only create on its way to raising `InconsistentHookExecution`.
- **Truthiness swaps.** `unmount`'s `is_mounted = None`, `update_shadow`'s `check_purity=None`,
  and `equivalent_within`'s `case _: return False` dropped (returning `None`):
  each value is only ever read for truthiness.
- **`Hooks.use_effect`'s initial `deps=None`** instead of `(object(),)`.
  `handle_effects` reruns an effect whose `new_deps` is `None` or differs from `deps`,
  and `None` differs from every tuple, so a mounting effect runs either way.
