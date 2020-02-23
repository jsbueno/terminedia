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

def ansi_colors_to_markup(text):
    def color_to_markup(match):
        foreground = background = ""
        setting_fg = setting_bg = 0
        for code in match.group(1).split(";"):
            if not code:
                continue
            if code == "39" and not setting_fg and not setting_bg:
                foreground = "DEFAULT"
            elif code == "49" and not setting_fg and not setting_bg:
                background = "DEFAULT"
            elif code == "38" and not setting_fg and not setting_bg:
                setting_fg = 1
            elif code == "48" and not setting_fg and not setting_bg:
                setting_bg = 1
            elif code == "2" and (setting_fg == 1 or setting_bg == 1):
                if setting_fg == 1:
                    setting_fg = 2
                    foreground = "("
                else:
                    setting_bg = 2
                    background = "("
            elif code == "5" and (setting_fg == 1 or setting_bg == 1):
                raise NotImplementedError("256 Color ANSI palette code not implmented in this parser")
            elif 2 <= setting_fg <= 4:
                setting_fg = setting_fg + 1 if setting_fg < 4 else 0
                foreground += code + (", " if setting_fg else ")")
            elif 2 <= setting_bg <= 4:
                setting_bg = setting_bg + 1 if setting_bg < 4 else 0
                background += code + (", " if setting_bg else ")")
        foreground = f"foreground: {foreground}" if foreground else ""
        background = f"background: {background}" if background else ""

        # yes - this is the first materialization of the planned
        # 'markup' for rich-printing in this project - it should be good
        # for comparing expected render results.
        return f"[{foreground}{'][' if foreground and background else ''}{background}]"
        # (multiple markups should be allowed in a single [] group, delimited by ";"
        #  however for the purpose of testing the different rendering methods
        # these are always rendered as different groups)

    return re.sub(r"\x1b\[([0-9;]+)m", color_to_markup, text)

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
def test_render_spaces_default_color():
    sc = TM.Screen(size=(3,3))
    sc.update()

    data = strip_ansi_seqs((yield None))
    assert data == TM.values.EMPTY * 9


@pytest.mark.parametrize(*fast_and_slow_render_mark)
@rendering_test
def test_render_blocks_default_color():

    FB = TM.values.FULL_BLOCK

    sc = TM.Screen(size=(3,3))
    sc.data[0,0] = FB
    sc.data[2,2] = FB
    sc.update()

    data = strip_ansi_seqs((yield None))

    assert data == FB + TM.values.EMPTY * 7 + FB

@pytest.mark.parametrize(*fast_and_slow_render_mark)
@rendering_test
def test_render_blocks_foreground_color():

    sc = TM.Screen(size=(3,3))
    sc.data.context.color = (255, 0, 0)
    sc.data[0,0] = "*"
    sc.data.context.color = (0, 255, 0)
    sc.data[1,0] = "*"
    sc.data.context.color = TM.DEFAULT_FG
    sc.data[2,0] = "*"
    sc.update()

    data = ansi_colors_to_markup(strip_ansi_movement((yield None)))
    breakpoint()
    assert data == "[foreground: (255, 0, 0)][background: DEFAULT]*[foreground: (0, 255, 0)]*[foreground: DEFAULT]*" + TM.values.EMPTY * 6
