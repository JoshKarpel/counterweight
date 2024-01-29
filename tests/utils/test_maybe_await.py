from counterweight.app import maybe_await


def foo() -> str:
    return "bar"


async def test_with_normal() -> None:
    assert await maybe_await(foo()) == "bar"


async def afoo() -> str:
    return "bar"


async def test_with_coroutine() -> None:
    # mypy can't seem to infer the type of `afoo()`, it thinks it's Awaitable[Never] ?
    assert await maybe_await(afoo()) == "bar"  # type: ignore[arg-type]
