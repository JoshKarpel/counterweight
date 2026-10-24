import pytest

from counterweight._output import clipboard_instructions


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        pytest.param("hello", "\x1b]52;c;aGVsbG8=\x1b\\", id="ascii"),
        pytest.param("日本 🇯🇵", "\x1b]52;c;5pel5pysIPCfh6/wn4e1\x1b\\", id="utf-8"),
        pytest.param("a\nb\x1b\\c\x07", "\x1b]52;c;YQpiG1xjBw==\x1b\\", id="control-characters"),
        pytest.param("", "\x1b]52;c;\x1b\\", id="empty"),
    ],
)
def test_clipboard_instructions_set_the_clipboard_to_the_base64_of_the_texts_utf_8(text: str, expected: str) -> None:
    assert clipboard_instructions(text) == expected
