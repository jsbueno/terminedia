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
    ("typed", "expected", "extra_kw", "shapped"), [
        ("ABC", "ABC", None, None),
        (f"ABC{K.LEFT}D", "ABDC", None, None),
        (f"ABC{K.LEFT + K.INSERT}D", "ABD", None, None),
        (f"ABC\rDEF", "ABC\nDEF", None, "ABC \nDEF \n    \n    "),
    ]
)
@rendering_test
def test_text_widget_sequence_write(typed, expected, extra_kw, shapped):
    stdin = io.StringIO()
    with patch("sys.stdin", stdin):
        sc = TM.Screen()
        with sc, TM.keyboard:
            w = TM.widgets.Text(sc, pos=(0,0), size=(4,4), **(extra_kw  or {}))
            sc.update()
            stdin.write(typed)
            stdin.seek(0)
            sc.update()

            yield None
            sc.update()
    #if "\r" in typed:
        #import rpdb; rpdb.set_trace()
        ##os.system("reset"); breakpoint()
    assert w.value == expected
    if shapped:
        value = TM.image.ShalowShapeRepr(w.shape).text()
        assert value == shapped
