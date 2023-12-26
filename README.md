[![PyPI](https://img.shields.io/pypi/v/counterweight)](https://pypi.org/project/counterweight)
[![PyPI - License](https://img.shields.io/pypi/l/counterweight)](https://pypi.org/project/counterweight)
[![Docs](https://img.shields.io/badge/docs-exist-brightgreen)](https://www.counterweight.dev)

[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/JoshKarpel/counterweight/main.svg)](https://results.pre-commit.ci/latest/github/JoshKarpel/counterweight/main)
[![codecov](https://codecov.io/gh/JoshKarpel/counterweight/branch/main/graph/badge.svg?token=2sjP4V0AfY)](https://codecov.io/gh/JoshKarpel/counterweight)

[![GitHub issues](https://img.shields.io/github/issues/JoshKarpel/counterweight)](https://github.com/JoshKarpel/counterweight/issues)
[![GitHub pull requests](https://img.shields.io/github/issues-pr/JoshKarpel/counterweight)](https://github.com/JoshKarpel/counterweight/pulls)

# Counterweight

Counterweight is an experimental text user interface (TUI) framework for Python,
inspired by [React](https://react.dev/) and [Tailwind CSS](https://tailwindcss.com/).

A TUI application built with Counterweight is a tree of declarative **components**,
each of which represents some piece of the UI by bundling together
a visual **element** along with its **state** and how that state should change due to **events** like user input.

As an application author,
you define the components and their relationships as a tree of Python functions.
You use **hooks** to manage state and side effects,
and **styles** to change how the elements look.

Counterweight takes this declarative representation of the UI and **renders** it to the terminal,
updating the UI when state changes in response to user input or side effects
(by calling your function tree).

## Installation

Counterweight is available [on PyPI](https://pypi.org/project/counterweight/):

```bash
pip install counterweight
```
