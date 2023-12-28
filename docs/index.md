# Counterweight

Counterweight is an experimental text user interface (TUI) framework for Python,
inspired by [React](https://react.dev/) and [Tailwind CSS](https://tailwindcss.com/).

A TUI application built with Counterweight is a tree of declarative
[**components**](components/index.md),
each of which represents some piece of the UI by bundling together
a visual [**element**](elements/index.md) along with its **state** and how that state should change due to
[**events**](input-handling/events.md) like user input.

As an application author,
you define the components and their relationships as a tree of Python functions.
You use [**hooks**](hooks/index.md) to manage state and side effects,
and [**styles**](styles/index.md) to change how the elements look.

Counterweight takes this declarative representation of the UI and **renders** it to the terminal,
updating the UI when state changes in response to user input or side effects
(by calling your function tree).

## Installation

Counterweight is available [on PyPI](https://pypi.org/project/counterweight/):

```bash
pip install counterweight
```
