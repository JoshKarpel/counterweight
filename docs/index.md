# Counterweight

Counterweight is an experimental text user interface (TUI) framework for Python,
inspired by [React](https://react.dev/) and [Tailwind CSS](https://tailwindcss.com/).

A TUI application built with Counterweight is a tree of declarative
[**components**](components/index.md),
each of which represents some piece of the UI.
As an application author,
you define the components and their relationships as a tree of Python functions.
You use [**Styles**](styles/index.md) to change how the components look,
and [**hooks**](hooks/index.md) to manage state and side effects.
Counterweight takes this declarative representation of the UI and **renders** it to the terminal,
updating the UI as needed when state changes in response to user input or side effects.

## Installation

Counterweight is available [on PyPI](https://pypi.org/project/counterweight/):

```bash
pip install counterweight
```
