import io
import re
from functools import wraps
from unittest import mock

import pytest
import terminedia.image as IMG
import terminedia as TM
from terminedia.values import DEFAULT_FG, Directions as D

def strip_ansi_seqs(text):
    return re.sub(r"\x1b\[[0-9;?]*?[a-zA-Z]", "", text)

def strip_ansi_movement(text):
    return re.sub(r"(\x1b\[[0-9;]+?[ABCDH]|\n)","", text, re.MULTILINE)

def strip_ansi_default_colors(text):
    return re.sub(r"\x1b\[([34]9;?)+m","", text, re.MULTILINE)

fast_and_slow_render_mark = ("set_render_method", [
    (lambda: setattr(TM.context, "fast_render", False)),
    (lambda: setattr(TM.context, "fast_render", True)),
])


def rendering_test(func):
    #@wraps(func)
    def rendering_test(set_render_method, DISPLAY, DELAY):
        set_render_method()
        stdout = io.StringIO()

        fn = func()
        with mock.patch("sys.stdout", stdout):
            next(fn)

        if DISPLAY:
            print(stdout.getvalue())
            TM.pause(DELAY)
        try:
            fn.send(stdout.getvalue())
        except StopIteration:
            pass
    rendering_test.__name__ = func.__name__

    return rendering_test

@pytest.mark.parametrize(*fast_and_slow_render_mark)
@rendering_test
def test_render_spaces_default_color_work():
    sc = TM.Screen(size=(3,3))
    sc.update()

    data = strip_ansi_seqs((yield None))
    assert data == TM.values.EMPTY * 9


@pytest.mark.parametrize(*fast_and_slow_render_mark)
@rendering_test
def test_render_blocks_default_color_work():

    FB = TM.values.FULL_BLOCK

    sc = TM.Screen(size=(3,3))
    sc.data[0,0] = FB
    sc.data[2,2] = FB
    sc.update()

    data = strip_ansi_seqs((yield None))

    assert data == FB + TM.values.EMPTY * 7 + FB
