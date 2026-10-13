from counterweight.styles.styles import Color


def test_blend_moves_each_channel_alpha_of_the_way_to_the_other_color() -> None:
    assert Color(10, 100, 200).blend(Color(250, 20, 60), alpha=0.25) == Color(70, 80, 165)


def test_blend_truncates_fractional_channels() -> None:
    assert Color(0, 0, 0).blend(Color(3, 5, 7), alpha=0.5) == Color(1, 2, 3)
