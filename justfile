#!/usr/bin/env just --justfile

set ignore-comments

[default]
[doc('List available recipes')]
list:
    just --list

alias l := list

[doc('Run a recipe whenever source files change')]
watch *CMD:
    uv run watchfiles --verbosity warning '{{ CMD }}' src/ tests/ docs/ examples/

alias w := watch

[doc('Stage updated files and run pre-commit hooks')]
pre-commit:
    git add --update
    uv run pre-commit

alias p := pre-commit

# --cov goes last because it takes an optional value, which would swallow a test path after it.
# Only a full run can reach the coverage floor, so any arguments (usually selecting tests) turn it off.
[doc('Run type checking, then the tests with coverage, passing any arguments on to pytest')]
[positional-arguments]
test *ARGS:
    uv run mypy
    uv run pytest -n auto --dist worksteal --failed-first "$@" --cov {{ if ARGS == "" { "" } else { "--cov-fail-under=0" } }}

alias t := test

[doc('Serve documentation locally, restarting when the config, a hook, a screenshot, or the logo changes')]
docs-serve PORT="8000":
    exec uv run watchfiles --target-type command 'mkdocs serve --dev-addr localhost:{{ PORT }}' mkdocs.yml mkdocs_hooks/ docs/assets/ codegen/generate_logo.py

alias d := docs-serve

# Two workers per CPU, because many tests mostly wait (on a program, a timeout), and a waiting worker holds its slot.
[doc('Run mutation testing, or re-run only the named mutants (globs work)')]
[positional-arguments]
mutate *MUTANTS:
    uv run mutmut run --max-children $(( {{ num_cpus() }} * 2 )) "$@"

[doc('Build documentation with strict mode')]
docs-build:
    uv run mkdocs build --strict

alias db := docs-build

[doc('Regenerate the style utility constants and the logo files in docs/assets/')]
codegen:
    uv run python codegen/generate_utilities.py
    uv run python codegen/generate_logo.py

alias c := codegen

[doc('Run the counterweight devlog')]
devlog *ARGS:
    @uv run counterweight devlog {{ ARGS }}

alias dl := devlog

# Without --blocking, Tachyon fails to read about 40% of samples, and not uniformly: it undercounts
# the shadow tree update and overcounts layout. --blocking slows frames by about 20%, so the frame
# times come from a second, unprofiled run, which overwrites the profiled run's.
[doc('Run a benchmark workload under Tachyon, then time it unprofiled and report on both')]
profile WORKLOAD NAME=WORKLOAD *ARGS:
    @mkdir -p profiles
    uv run python -m profiling.sampling run --blocking --binary -o profiles/{{ NAME }}.bin -m benchmarks run {{ WORKLOAD }} --name {{ NAME }} {{ ARGS }}
    uv run python -m benchmarks run {{ WORKLOAD }} --name {{ NAME }} {{ ARGS }}
    uv run python -m profiling.sampling replay --flamegraph -o profiles/{{ NAME }}.html profiles/{{ NAME }}.bin
    uv run python -m benchmarks report {{ NAME }}

# Binds every interface so a remote machine's HTTPS proxy (such as exe.dev's, which forwards ports 3000-9999) can reach it.
[doc('Serve the profiles directory (flamegraphs and reports) over HTTP')]
profiles-serve PORT="8001":
    @mkdir -p profiles
    exec uv run python -m http.server {{ PORT }} --bind 0.0.0.0 --directory profiles

# --local keeps mise from upgrading the tools in your global config too.
[doc('Upgrade all dependencies, and the tools in mise.toml')]
upgrade:
    uv lock --upgrade
    mise upgrade --local --bump
    mise lock

alias update := upgrade
alias u := upgrade
