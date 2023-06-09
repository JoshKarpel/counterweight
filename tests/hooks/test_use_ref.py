from reprisal.hooks import Anchor, use_ref


def test_ref_is_the_same_between_runs() -> None:
    def _() -> list[int]:
        return use_ref([1]).current

    anchor = Anchor(_)

    a = anchor()
    assert a == [1]

    a.append(2)

    b = anchor()
    assert b == [1, 2]
    assert a is b
