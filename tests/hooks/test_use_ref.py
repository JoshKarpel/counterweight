from reprisal.hooks import HookContext, use_ref


def test_ref_is_the_same_between_runs() -> None:
    def _() -> list[int]:
        return use_ref([1]).current

    ctx = HookContext(_)

    a = ctx()
    assert a == [1]

    a.append(2)

    b = ctx()
    assert b == [1, 2]
    assert a is b
