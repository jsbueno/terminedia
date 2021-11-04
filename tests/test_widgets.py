import terminedia as TM
from terminedia.values import WIDTH_INDEX, HEIGHT_INDEX, RelativeMarkIndex
from terminedia.input import KeyCodes as K

import pytest

from conftest import rendering_test, fast_render_mark, fast_and_slow_render_mark

from unittest.mock import patch
import os, io

@pytest.mark.parametrize(*fast_render_mark)
@pytest.mark.parametrize(
    ("typed", "expected", "extra_kw"), [
        ("ABC", "ABC", None),
        (f"ABC{K.LEFT}D", "ABDC", None),
        (f"ABC{K.LEFT + K.INSERT}D", "ABD", None),
        (f"ABC{K.LEFT + K.LEFT}D", "ADBC", None),
    ]
)
@rendering_test
def test_entry_widget_sequence_write(typed, expected, extra_kw):
    stdin = io.StringIO()
    with patch("sys.stdin", stdin):
        sc = TM.Screen()
        with sc, TM.keyboard:
            w = TM.widgets.Entry(sc, pos=(0,0), width=5, **(extra_kw  or {}))
            sc.update()
            stdin.write(typed)
            stdin.seek(0)
            sc.update()

            yield None
            sc.update()
    assert w.value == expected


@pytest.mark.parametrize(*fast_render_mark)
@pytest.mark.parametrize(
    ("typed", "expected", "extra_kw", "shaped"), [
        ("ABC", "ABC", None, None),
        (f"ABC{K.LEFT}D", "ABDC", None, None),
        (f"ABC{K.LEFT + K.INSERT}D", "ABD", None, None),
        (f"ABC\rDEF", "ABC\nDEF", None, "ABC \nDEF \n    \n    "),
        (f"ABC\rDEF", "ABC\nDEF", {"text_plane": 4}, "ABC \nDEF \n    \n    "),
        (f"ABC\rDEF{K.UP}G", "ABCG\nDEF", None, "ABCG\nDEF \n    \n    "),
        (f"ABC\rDEF{K.UP + K.LEFT}G", "ABGC\nDEF", None, "ABGC\nDEF \n    \n    "),
        (f"ABC\rDEF{K.UP + K.LEFT + K.INSERT}G", "ABG\nDEF", None, "ABG \nDEF \n    \n    "),
        (f"{K.DOWN + K.DOWN}ABC", "\n\nABC", None, "    \n    \nABC \n    "), ## Failing - tough it works interactivelly. Maybe somethinbg meant to deduplicate keystrokes is removing the second Down arrow??. Returns "\nABC"
        (f"{K.DOWN + K.INSERT + K.INSERT + K.DOWN}ABC", "\n\nABC", None, "    \n    \nABC \n    "), # Workaround for the previous test: don't send 2 K.DOWN in sequence.
        (f"{K.DOWN + ' ' + K.DOWN}ABC", "\n \nABC", None, "    \n    \nABC \n    "),
    ]
)
@rendering_test
def test_text_widget_sequence_write(typed, expected, extra_kw, shaped):
    extra_kw = extra_kw or {}
    stdin = io.StringIO()
    with patch("sys.stdin", stdin):
        sc = TM.Screen()
        with sc, TM.keyboard:
            w = TM.widgets.Text(sc, pos=(0,0), size=(4,4), **extra_kw)
            sc.update()
            stdin.write(typed)
            stdin.seek(0)
            sc.update()

            yield None
            sc.update()
    assert w.value == expected
    if shaped:
        value = w.shape.text[extra_kw.get("text_plane", 1)].shaped_str
        assert value == shaped
