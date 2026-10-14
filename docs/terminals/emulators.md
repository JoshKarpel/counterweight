# Emulators and Pseudo-Terminals

[One-shot commands](commands.md) are built from two lower layers, which this page covers for code that needs them directly:
a pseudo-terminal, which runs a program as a terminal window does and hands back the bytes it writes,
and a terminal emulator, which turns those bytes into what the terminal shows.
Neither knows about the other, so output recorded ahead of time can be fed to an emulator with no program run,
and a program's output can go somewhere other than an emulator.

They need the `emulator` extra (`counterweight[emulator]`), and pseudo-terminals need Linux or macOS.

## Pseudo-terminals

[`run_pty`][counterweight.pseudoterminal.run_pty] runs a program on a new pseudo-terminal until it exits,
in its own session with the terminal as its controlling terminal,
calling `on_output` with what the program writes, standard output and standard error together.
It returns how the program exited ([`Exited`][counterweight.programs.Exited]),
or why it couldn't start ([`FailedToStart`][counterweight.programs.FailedToStart]),
and hands out a [`PtyConnection`][counterweight.pseudoterminal.PtyConnection] that writes to the program
without blocking and resizes its terminal.
Cancelling it hangs the program up, as closing a terminal window does.

[`use_pty`][counterweight.pseudoterminal.use_pty] runs a program while its component is mounted,
as a terminal window or a multiplexer's pane does:
it starts once its size is positive, resizes the terminal as its size changes,
and starts the program again when its `argv` or environment change.

## Emulators

An [`Emulator`][counterweight.emulator.Emulator] is fed the bytes a program writes,
answers the program's queries through `on_reply`,
and [`snapshot`][counterweight.emulator.Emulator.snapshot] turns what its terminal shows
into an immutable [`Screen`][counterweight.emulator.Screen].
A snapshot of a terminal that didn't change is the same `Screen` as before,
and rows that didn't change are shared between snapshots, so a canvas drawing one redraws only when it changed.
[`scrolled_off`][counterweight.emulator.Emulator.scrolled_off] returns the rows that scrolled off the top of the screen
since it was last called, for an emulator given a `scrollback`.

[`ScreenView`][counterweight.painters.terminal.ScreenView] is the [`Canvas`](../elements/canvas.md) painter
that draws a `Screen`, with its cursor when asked,
and [`Transcript`][counterweight.painters.terminal.Transcript] the one that draws
everything a program printed.

## API

::: counterweight.pseudoterminal.run_pty
::: counterweight.pseudoterminal.PtyConnection
::: counterweight.pseudoterminal.StandardInput
::: counterweight.pseudoterminal.use_pty
::: counterweight.pseudoterminal.Pty
::: counterweight.pseudoterminal.PtyStatus
::: counterweight.pseudoterminal.Starting
::: counterweight.pseudoterminal.Running
::: counterweight.emulator.Emulator
::: counterweight.emulator.Screen
::: counterweight.emulator.Modes
::: counterweight.emulator.MouseTracking
::: counterweight.emulator.MAX_SCROLLBACK
::: counterweight.painters.terminal.ScreenView
