# Under the Hood

This section is for those who want to know more about how Counterweight's internals work.

## Inspirations

Counterweight is inspired by a variety of existing frameworks and libraries:

- [React](https://react.dev/) - state and side effect management via hooks, component tree,
  [declarative/immediate-mode UI](https://en.wikipedia.org/wiki/Immediate_mode_(computer_graphics))
- [Tailwind CSS](https://tailwindcss.com/) - utility styles on top of a granular CSS-like framework
- [Textual](https://textual.textualize.io/) - rendering to the terminal without going through something like
  [curses](https://docs.python.org/3/library/curses.html#module-curses), CSS-like styles

## Data Flow

```mermaid
flowchart TB

    en[Entrypoint]
    r[Render]
    l[Layout]
    p[Paint]

    subgraph Output
        ph[Paint History]
        dp[Overlay & Diff Paint]
        d[Apply Paint]
        t[Terminal Output]
    end

    subgraph Input
        i[Keyboard/Mouse Input]
        vp[Parse VT Commands]
        ev[Populate Event Stream]
        eh[Call Event Handlers]
    end

    subgraph Effects
        efm[Mount/Unmount Effects]
        eff[Mounted Effects]
    end

    en -- Initial Render --> r
    r -- Shadow Tree --> l
    l -- Layout Tree --> p
    p -- Paint --> dp

    ph -- Previous Paint --> dp
    dp -- Store Current Paint --> ph
    dp -- Diffed Paint --> d

    d -- VT Commands --> t

    i -- VT Commands --> vp
    vp -- Keys/Mouse Position --> ev
    ev -- Events --> eh
    l -- Handler Tree --> eh
    p -- Event Targets --> eh

    eh -- Set State --> r

    l -- Mounted Components --> efm
    efm --> eff
    eff -- Set State --> r
```
