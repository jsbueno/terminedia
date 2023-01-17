import terminedia as TM
from terminedia.values import WIDTH_INDEX, HEIGHT_INDEX, RelativeMarkIndex
from terminedia.input import KeyCodes as K

import pytest

from conftest import rendering_test, fast_render_mark, fast_and_slow_render_mark

from unittest.mock import patch
import os, io

M=TM.Mark

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
        P(f"{K.RIGHT * 3}ABCD", "ABCD", None, id="insert_from_midle_of_line_collapses_white_space_at_left"),
        P(f"{K.RIGHT * 3 + K.INSERT}ABCD", "   AD", None, id="replace_from_midle_of_line_preserves_white_space_at_left"),
        P("ABCDEFG", "ABCDEFG", {"text_size": 10}, id="larger_than_displayed_text_entry"),
        P(f"ABCD{K.LEFT * 2}EFG", "ABEFGCD", {"text_size": 10}, id="larger_than_displayed_text_entry_insert_middle"),
        P(f"ABCDE{K.LEFT * 2}{K.DELETE}", "ABDE", None, id="del_works_for_fitting_text"),
        P(f"ABCDEFGH{K.LEFT * 2}{K.DELETE}", "ABCDEFH", {"text_size": 10}, id="del_works_for_larger_than_displayed_text_plain"),
        P(f"ABCDE{K.LEFT * 2}FG{K.LEFT}{K.DELETE}", "ABCFDE", {"text_size": 10}, id="del_works_for_larger_than_displayed_text_out_of_screen"),
        P(f"ABCDEFG{K.LEFT*7}HI", "HIABCDEFG", {"text_size": 10}, id="larger_than_displayed_text_entry_can_edit_first_position"),
        P(f"ABCDEFG{K.LEFT*7}HI{K.RIGHT*7}JKL", "HIABCDEFGJKL", {"text_size": 15}, id="larger_than_displayed_text_entry_can_edit_first_position_and_go_back_to_end"),
        P(f"ABCDEFG{K.LEFT*7}HI{K.RIGHT*5}JKL", "HIABCDEFJKLG", {"text_size": 15}, id="larger_than_displayed_text_entry_can_edit_first_position_and_go_back_to_one_before_end"),
        P(f"ABCDEFG{K.BACK * 6}", "A", {"text_size": 10}, id="backspace_works_for_larger_than_displayed_text_plain"),
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
    ("typed", "extra_kw"), [
        P("ABC", {}, id="plain"),
        P(f"ABCDE", {}, id="full"),
        P("ABCDEFG", {"text_size": 10}, id="larger_than_displayed_text_entry_scrolled_left"),
        P(f"ABCD{K.LEFT * 2}EFG", {"text_size": 10}, id="larger_than_displayed_text_entry_scroleed_right"),
    ]
)
@rendering_test
def test_entry_widget_clear(typed, extra_kw):
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
    w.clear()
    assert w.value == ""


@pytest.mark.parametrize(*fast_render_mark, ids=["fast"])
@pytest.mark.parametrize(
    ("typed", "expected", "extra_kw", "rendered"), [
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
        P(f"ABCDEFGHI", "ABCDEFGHI", None, "ABCD\nEFGH\nI   \n    ", id="plain_three_lines_no_break"),
        P(f"ABCDEFGHIJKLMNOPQ", "ABCDEFGHIJKLMNOP", None, "ABCD\nEFGH\nIJKL\nMNOP", id="plain_full_widget_typed_no_break"),
        P(f"ABCDEFGHI", "ABCDEF", {"marks": {(2,0): M(direction="down")}}, "ABC \n  D \n  E \n  F ", id="embeded_direction_change_turn_down"),
        P(f"A\rBCDEFGHI", "A\nBCDE", {"marks": {(2,0): M(direction="down")}}, "A B \n  C \n  D \n  E ", id="embeded_direction_change_turn_down_with_line_break"),
        P(f"ABCD{K.BACK + K.BACK}EF", "ABEF", {"marks": {(2,0): M(direction="down")}}, "ABE \n  F \n    \n    ", id="embeded_direction_change_turn_down_backspace"),
        P(f"A\rB{K.BACK + K.BACK}CDEF", "ACDEF", {"marks": {(2,0): M(direction="down")}}, "ACD \n  E \n  F \n    ", id="embeded_direction_change_turn_down_line_break_backspace"),
        P(f"ABCDEFGHIJKLMNOPQRST", "ABCDEFGHIJKLMNOPQRST", {"text_size": 20}, "EFGH\nIJKL\nMNOP\nQRST", id="text_size_larger_than_displayed"),
        P(f"ABCDEF{K.LEFT * 4}GHI", "ABGHICDEF", None, "ABGH\nICDE\nF   \n    ", id="navigate_left_arrow_goes_previous_line"),
        P(f"ABCDEF{K.LEFT * 4}GHI{K.RIGHT * 4}JKL", "ABGHICDEFJKL", None, "ABGH\nICDE\nFJKL\n    ", id="navigate_right_arrow_goes_next:_line"),
        P(f"A\r\r\rD\rE", "A\n\n\nD\nE", {"text_size": 24}, "    \n    \nD   \nE   ", id="larger_than_displayed_text_should_scroll_up_with_enter_on_last_line"),
        P(f"A\r\r\r\rD", "A\n\n\n\nD", {"text_size": 24}, "    \n    \n    \nD   ", id="larger_than_displayed_text_should_scroll_up_with_enter_on_empty_last_line"),
        P(f"A\r\r\rD{K.UP}\r", "A\n\n\n\nD", {"text_size": 24}, "A   \n    \n    \n    ", id="larger_than_displayed_text_should_scroll_down_with_enter_before_last_line"),
        P(f"A\r\r\rD{K.UP * 5 + K.LEFT}Z\r", "Z\nA\n\n\nD", {"text_size": 24}, "Z   \nA   \n    \n    ", id="larger_than_displayed_text_can_scroll_back_to_top"),
        P(f"A\r\r\r\rD{K.UP * 5 + K.LEFT}Z\r", "Z\nA\n\n\n\nD", {"text_size": 24}, "Z   \nA   \n    \n    ", id="larger_than_displayed_text_can_scroll_back_to_top_with_extra_line"),
        P(f"A\r\r\r\rD{K.UP * 5 + K.LEFT}Z\r{K.DOWN * 6 + K.RIGHT}\rY", "Z\nA\n\n\n\nD\nY", {"text_size": 24}, "    \n    \nD   \nY   ", id="larger_than_displayed_text_can_scroll_back_to_top"),
    ]
)
@rendering_test
def test_text_widget_sequence_write(typed, expected, extra_kw, rendered):
    extra_kw = extra_kw or {}
    stdin = io.StringIO()
    marks = extra_kw.pop("marks", None)
    with patch("sys.stdin", stdin):
        sc = TM.Screen()
        with sc, TM.keyboard:
            if marks:
                sp = sc.sprites.add((4,4))
                sp.shape.text[1].marks.update(marks)
                extra_kw["sprite"] = sp
            else:
                extra_kw["size"] = (4, 4)

            w = TM.widgets.Text(sc, pos=(0,0), **extra_kw)
            sc.update()
            stdin.write(typed)
            stdin.seek(0)
            sc.update()

            yield None
            sc.update()
    if expected:
        assert w.value == expected
    if rendered:
        value = w.editable.shaped_value
        assert value == rendered



s_opt = ["AAA", "BBB", "CCC"]


@pytest.mark.parametrize(*fast_render_mark, ids=["fast"])
@pytest.mark.parametrize(
    ("options", "typed", "expected", "extra_kw", "rendered"), [
        P(s_opt, K.ENTER, "AAA", None, None, id="imediate"),
        P(s_opt, f"{K.DOWN + K.ENTER}", "BBB", None, None, id="second_opt"),
        P(s_opt, f"{K.DOWN * 3 + K.ENTER}", "CCC", None, None, id="stop_on_last_opt"),
        P(s_opt, f"{K.DOWN * 3 + K.UP + K.ENTER}", "BBB", None, None, id="move_back_up"),
        P(s_opt, "", None, None, "AAA\nBBB\nCCC", id="adaptive_min_width"),
        P(s_opt, "", None, {"min_width": 5}, " AAA \n BBB \n CCC ", id="center_align"),
        P(s_opt, "", None, {"min_width": 5, "align":"left"}, "AAA  \nBBB  \nCCC  ", id="left_align"),
        P(s_opt, "", None, {"min_width": 5, "align":">"}, "  AAA\n  BBB\n  CCC", id="right_align"),
        P([TM.Color("red"), TM.Color("green")], f"{K.DOWN + K.ENTER}", TM.Color("green"), {"min_width": 5}, None, id="color_select"),
    ]
)
@rendering_test
def test_selector_widget(options, typed, expected, extra_kw, rendered):
    extra_kw = extra_kw or {}
    stdin = io.StringIO()
    max_height = extra_kw.pop("max_height", 4)
    max_width = extra_kw.pop("max_width", 5)
    with patch("sys.stdin", stdin):
        sc = TM.Screen()
        with sc, TM.keyboard:
            w = TM.widgets.Selector(sc, options, pos=(0,0), max_height=max_height, max_width=max_width,**(extra_kw  or {}))
            sc.update()
            stdin.write(typed)
            stdin.seek(0)
            sc.update()

            yield None
            sc.update()
    if expected:
        assert w.value == expected
    if rendered:
        value = w.shape.text[extra_kw.get("text_plane", 1)].shaped_str
        assert value == rendered

