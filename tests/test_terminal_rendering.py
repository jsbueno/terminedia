import io
import re
from unittest import mock

import pytest
import terminedia as TM
from terminedia.values import TRANSPARENT, EMPTY

from conftest import rendering_test, fast_and_slow_render_mark


def strip_ansi_seqs(text):
    return re.sub(r"\x1b\[[0-9;?]*?[a-zA-Z]", "", text)


def strip_ansi_movement(text):
    return re.sub(r"(\x1b\[[0-9;]+?[ABCDH]|\n)", "", text, re.MULTILINE)


def strip_ansi_default_colors(text):
    return re.sub(r"\x1b\[([34]9;?)+m", "", text, re.MULTILINE)


def ansi_colors_to_markup(text):
    # FIXME - if this is ever promoted to a generic ANSI stream parser,
    # The effects on/off codes are on terminal.py.
    # For testing purposes we are going with these:
    BLINK = "5"
    NOBLINK = "25"
    other_effect_off_codes = "22;23;24;27;22;25;28;29;24;55;23".split(";")

    def color_to_markup(match):
        foreground = background = effects = ""
        setting_fg = setting_bg = 0
        for code in match.group(1).split(";"):
            if not setting_bg and not setting_fg:
                if code == "39":
                    foreground = "DEFAULT"
                elif code == "49":
                    background = "DEFAULT"
                elif code == "38":
                    setting_fg = 1
                elif code == "48":
                    setting_bg = 1
                elif code == BLINK:
                    effects = "BLINK"
                elif code == NOBLINK:
                    effects = "NOBLINK"
                elif code in other_effect_off_codes:
                    # classic rendering will always send effect-off code for all other effects
                    # when rendering any effect
                    pass
                continue
            if code == "2" and (setting_fg == 1 or setting_bg == 1):
                if setting_fg == 1:
                    setting_fg = 2
                    foreground = "("
                else:
                    setting_bg = 2
                    background = "("
            elif code == "5" and (setting_fg == 1 or setting_bg == 1):
                raise NotImplementedError(
                    "256 Color ANSI palette code not implmented in this parser"
                )
            elif 2 <= setting_fg <= 4:
                setting_fg = setting_fg + 1 if setting_fg < 4 else 0
                foreground += code + (", " if setting_fg else ")")
            elif 2 <= setting_bg <= 4:
                setting_bg = setting_bg + 1 if setting_bg < 4 else 0
                background += code + (", " if setting_bg else ")")
            else:
                return f"[ERROR in color code string: \\x1b[{match.group(1)}m"
        foreground = f"[foreground: {foreground}]" if foreground else ""
        background = f"[background: {background}]" if background else ""
        effects = f"[effects: {effects}]" if effects else ""

        # yes - this is the first materialization of the planned
        # 'markup' for rich-printing in this project - it should be good
        # for comparing expected render results.
        return f"{foreground}{background}{effects}"
        # (multiple markups should be allowed in a single [] group, delimited by ";"
        #  however for the purpose of testing the different rendering methods
        # these are always rendered as different groups)

    return re.sub(r"\x1b\[([0-9;]+)m", color_to_markup, text)

def ansi_movement_to_markup(text):
    def movement_to_markup(match):
        if match.group(1) == "\n":
            return "[MOVE NEW LINE]"
        if match.group(1) == "\n":
            return "[MOVE TAB]"
        tag = {
            "A": "MOVE UP",
            "B": "MOVE DOWN",
            "C": "MOVE RIGHT",
            "D": "MOVE LEFT",
            "H": "MOVE TO"
        } [match.group(3)]
        if tag == "MOVE TO":
            y, x = map(int, match.group(2).split(";"))
            result = f"[{tag}: {x + 1}, {y + 1}]"
        else:
            amount = f": {match.group(2)}" if match.group(2) else ""
            result = f"[{tag}{amount}]"
        return result
    return re.sub(r"(\x1b\[([0-9;]*)([ABCDH])|\n|\t)", movement_to_markup, text)


@pytest.mark.parametrize(*fast_and_slow_render_mark)
@rendering_test
def test_render_spaces_default_color():
    sc = TM.Screen(size=(3, 3))
    sc.update((0, 0))

    data = strip_ansi_seqs((yield None))
    assert data == TM.values.EMPTY * 9


@pytest.mark.parametrize(*fast_and_slow_render_mark)
@rendering_test
def test_render_blocks_default_color():

    FB = TM.values.FULL_BLOCK

    sc = TM.Screen(size=(3, 3))
    sc.data[0, 0] = FB
    sc.data[2, 2] = FB
    sc.update((0, 0))

    data = strip_ansi_seqs((yield None))

    assert data == FB + TM.values.EMPTY * 7 + FB


@pytest.mark.parametrize(*fast_and_slow_render_mark)
@rendering_test
def test_render_blocks_foreground_color():

    sc = TM.Screen(size=(3, 3))
    sc.data.context.color = (255, 0, 0)
    sc.data[0, 0] = "*"
    sc.data.context.color = (0, 1.0, 0)
    sc.data[1, 0] = "*"
    sc.data.context.color = TM.DEFAULT_FG
    sc.data[2, 0] = "*"
    sc.update((0, 0))

    data = ansi_colors_to_markup(strip_ansi_movement((yield None)))
    assert (
        data
        == "[foreground: (255, 0, 0)][background: DEFAULT]*[foreground: (0, 255, 0)]*[foreground: DEFAULT]*"
        + TM.values.EMPTY * 6
    )


@pytest.mark.parametrize(*fast_and_slow_render_mark)
@rendering_test
def test_render_blocks_background_color():

    sc = TM.Screen(size=(3, 3))
    sc.data.context.color = (255, 0, 0)
    sc.data.context.background = (255, 0, 0)
    sc.data[0, 0] = "*"
    sc.data.context.color = (0, 255, 0)
    sc.data[1, 0] = "*"
    sc.data.context.background = TM.DEFAULT_BG
    sc.data[2, 0] = "*"
    sc.update((0, 0))

    data = ansi_colors_to_markup(strip_ansi_movement((yield None)))
    assert (
        data
        == "[foreground: (255, 0, 0)][background: (255, 0, 0)]*[foreground: (0, 255, 0)]*[background: DEFAULT]*[foreground: DEFAULT]"
        + TM.values.EMPTY * 6
    )


@pytest.mark.parametrize(*fast_and_slow_render_mark)
@rendering_test
def test_render_effects_work():

    sc = TM.Screen(size=(3, 3))
    sc.context.effects = TM.Effects.blink
    sc.data[0, 0] = "a"
    sc.context.effects += TM.Effects.encircled
    sc.data[1, 0] = "a"
    sc.context.effects -= TM.Effects.blink
    sc.data[2, 0] = "a"
    sc.update((0, 0))

    data = ansi_colors_to_markup(strip_ansi_movement((yield None)))
    assert (
        data
        == "[foreground: DEFAULT][background: DEFAULT][effects: BLINK]a\u24d0[effects: NOBLINK]\u24d0"
        + TM.values.EMPTY * 6
        or data
        == "[foreground: DEFAULT][background: DEFAULT][effects: BLINK]a[effects: BLINK]\u24d0[effects: NOBLINK]\u24d0[effects: NOBLINK]      "
    )
    # The second form is used in classic rendering - it will reissue the existing effects for each character
    # (at least in this wide-char situation). It is not wrong, but is one of the reasons we needed a "fast rendering".



@pytest.mark.parametrize(*fast_and_slow_render_mark)
@rendering_test
def test_render_transparent_characters_dont_overwrite_terminal_contents():

    sc = TM.Screen(size=(3, 3))
    sc.data.clear(transparent=True)
    sc.data[1,1] = "*"
    sc.update((0, 0))

    data = ansi_movement_to_markup((yield None))
    assert data.count("*", 1)

    # Actual render optimizations won't place a 'move' for each non displayed pixel.
    # assert data.count("[MOVE") == 8
    assert re.sub(r"\[.+?\]", "", data).count(EMPTY) == 0
