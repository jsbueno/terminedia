import terminedia as TM
from terminedia.values import WIDTH_INDEX, HEIGHT_INDEX, RelativeMarkIndex
from terminedia.input import KeyCodes as K

import pytest

from conftest import rendering_test, fast_render_mark, fast_and_slow_render_mark

from unittest.mock import patch
import os, io

P = pytest.param

@pytest.mark.parametrize(*fast_render_mark, ids=["fast"])
@pytest.mark.parametrize(
    ("typed", "expected", "extra_kw"), [
        P("ABC", "ABC", None, id="plain"),
        P(f"ABC{K.LEFT}D", "ABDC", None, id="left_movement_insert"),
        P(f"ABC{K.LEFT + K.INSERT}D", "ABD", None,id="left_movement_replace"),
        P(f"ABC{K.LEFT + K.LEFT}D", "ADBC", None, id="double_left_movement"),
        P(f"A{K.LEFT + K.LEFT}BCD", "BCDA", None, id="double_left_movement_hit_start"),
        P(f"ABCDEF", "ABCDE", None, id="overflow"),
        P(f"ABCDE{K.INSERT}FG", "ABCDG", None, id="overflow_replace_last"),
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


@pytest.mark.parametrize(*fast_render_mark, ids=["fast"])
@pytest.mark.parametrize(
    ("typed", "expected", "extra_kw", "shaped"), [
        P("ABC", "ABC", None, None, id="plain_single_line"),
        P(f"ABC{K.LEFT}D", "ABDC", None, None, id="left_movement_insert"),
        P(f"ABC{K.LEFT + K.INSERT}D", "ABD", None, None,id="left_movement_replace"),
        P(f"ABC\rDEF", "ABC\nDEF", None, "ABC \nDEF \n    \n    ", id="plain_line_break"),
        P(f"ABC\rDEF", "ABC\nDEF", {"text_plane": 4}, "ABC \nDEF \n    \n    ", id="plain_single_line_plane_4"),
        P(f"ABC\rDEF{K.UP}G", "ABCG\nDEF", None, "ABCG\nDEF \n    \n    ", id="line_break_up_movement_insert"),
        P(f"ABC\rDEF{K.UP + K.LEFT}G", "ABGC\nDEF", None, "ABGC\nDEF \n    \n    ", id="line_break_up_left_movement_insert"),
        P(f"ABC\rDEF{K.UP + K.LEFT + K.INSERT}G", "ABG\nDEF", None, "ABG \nDEF \n    \n    ", id="line_break_up_left_movement_replace"),
        P(f"{K.DOWN + K.DOWN}ABC", "\n\nABC", None, "    \n    \nABC \n    ", id="down_movement_line_break"),
        P(f"{K.DOWN + K.INSERT + K.INSERT + K.DOWN}ABC", "\n\nABC", None, "    \n    \nABC \n    ", id="down_movement_line_break_roundtrip_insert"),
        P(f"{K.DOWN + ' ' + K.DOWN}ABC", "\n \nABC", None, "    \n    \nABC \n    ", id="stepped_down_movement_line_break"),
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
