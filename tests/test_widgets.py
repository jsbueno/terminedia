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
        P(f"ABCDEFG{K.LEFT*7}HI{K.RIGHT*5}JKL", "HIABCDEJKLFG", {"text_size": 15}, id="larger_than_displayed_text_entry_can_edit_first_position_and_go_back_to_one_before_end"),
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
        P(f"ABCDEFGHIJKLMNOPQ", "ABCDEFGHIJKLMNOP", None, "ABCD\nEFGH\nIJKL\nMNOP", id="plain_fulle_widget_typed_no_break"),
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
        P(f"AB\r\rCD{K.UP + K.DELETE}", "AB\nCD", None, "AB  \nCD  \n    \n    ", id="DEL_on_end_of_line_should_join_lines"),
        P(f"AB\r\rCD\rEF\rGH\rIJ{K.UP * 3 + K.DELETE}", "AB\nCD\nEF\nGH\nIJ", {"text_size": 24}, "AB  \nCD  \nEF  \nGH  ", id="DEL_on_end_of_line_should_join_lines_with_suffix_text"),
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


def test_softlines_physical_write_reflected_on_text_plane():
    sh = TM.shape((4,4))
    sl = TM.widgets.text.SoftLines(sh.text[1])
    assert sh.text[1][2,2] == " "
    sl.physical_cells[2,2] = "A"
    assert sh.text[1][2,2] == "A"


def test_softlines_initial_default_value_is_empty():
    sh = TM.shape((4,4))
    sl = TM.widgets.text.SoftLines(sh.text[1])
    assert len(sl.value) == 0
    assert len(sl) == 0

def test_softlines_single_line_value_preserved_short_line():
    sh = TM.shape((4,4))
    sl = TM.widgets.text.SoftLines(sh.text[1], "ABC")
    assert sl.value == "ABC"

def test_softlines_single_line_value_preserved_long_line():
    sh = TM.shape((4,4))
    sl = TM.widgets.text.SoftLines(sh.text[1], "Hello World")
    assert sl.value == "Hello World"

def test_softlines_single_line_break_preserved():
    sh = TM.shape((4,4))
    sl = TM.widgets.text.SoftLines(sh.text[1], "ABC\nDEF")
    assert sl.value == "ABC\nDEF"

def test_softlines_value_larger_than_displayed_single_line():
    sh = TM.shape((3,3))
    sl = TM.widgets.text.SoftLines(sh.text[1], "0123456789", max_text_size=20)
    assert sl.last_line_length == 9
    assert sl.displayed_value == "012345678"

def test_softlines_value_larger_than_displayed_multi_lines():
    sh = TM.shape((3,3))
    sl = TM.widgets.text.SoftLines(sh.text[1], "012\n345\n678\n9", max_text_size=20)
    #assert sl.last_line_length == 3
    assert sl.displayed_value == "012\n345\n678\n"
    assert sl.value == "012\n345\n678\n9"
    assert sl.post == ["9"]


def test_softlines_value_too_large_errors():
    sh = TM.shape((3,3))
    with pytest.raises(IndexError):
        sl = TM.widgets.text.SoftLines(sh.text[1], "0123456789")

def test_softlines_value_too_large_errors_even_with_custom_text_size():
    sh = TM.shape((3,3))
    sl = TM.widgets.text.SoftLines(sh.text[1], "0123456789", max_text_size=10)
    with pytest.raises(IndexError):
        sl = TM.widgets.text.SoftLines(sh.text[1], "0123456789A", max_text_size=10)


@pytest.mark.parametrize(["text", "offset", "expected_displayed",  "expected_pre", "expected_post"], [
    P("012345678", 0, "012345678", [], [], id="nop"),
    P("012345678", 1, "12345678", [], [], id="scroll_1_char_left"),
    P("012345678", 3, "345678", [], [], id="scroll_multi_chars_left"),
    P("0\n12345678", 1, "12345678", ["0"], [], id="scroll_1_line_left"),
    P("012\n345678", 4, "45678", ["012"], [], id="scroll_1_line_1_char_left"),
    P("012345678901", 3, "345678901", [], [], id="scroll_multi_char_left_pulling_from_post_same_line"),
    P("012\n345678\n901\n234", 3, "345678\n901\n", ["012"], ["234"], id="scroll_multi_char_left_pulling_from_post_line_breaks"),
])
def test_softlines_reflow(text, offset, expected_displayed, expected_pre, expected_post):
    sh = TM.shape((3,3))
    sl = TM.widgets.text.SoftLines(sh.text[1], text, max_lines=20)
    sl.offset = offset
    sl.reflow()
    assert sl.displayed_value == expected_displayed
    assert sl.pre == expected_pre
    assert sl.post == expected_post
    assert sl.value == text

@pytest.mark.parametrize(["text", "nchars", "expected_displayed", "expected_hard_lines"], [
    P("012", 1, "12", ["12 ", "   ", "   "], id="1_char"),
    P("012", 2, "2", ["2  ", "   ", "   "], id="2_chars"),
    P("012\n345", 2, "2\n345", ["2  ", "345", "   "], id="2_lines_2_chars"),
    P("012\n345", 3, "345", ["345", "   ", "   "], id="2_lines_consume_1st_line"),
    P("012\n345678901234", 4, "456789012", ["456", "789", "012"], id="consume_1st_line_pull_post_text"),
    P("012\n345678\n901234", 4, "45678\n901", ["456", "78 ", "901"], id="consume_1st_line_line_break"),
])
def test_softlines_scroll_characters_left(text, nchars, expected_displayed, expected_hard_lines):
    sh = TM.shape((3,3))
    sl = TM.widgets.text.SoftLines(sh.text[1], text, max_text_size=20)
    sl.scroll_char_left(nchars)
    assert sl.value == text
    assert sl.displayed_value == expected_displayed
    if expected_hard_lines:
        assert [line.value for line in sl.hard_lines] == expected_hard_lines

@pytest.mark.parametrize(["text", "initial_offset", "nchars", "expected_displayed"],  [
    P("012", 1, 1, "012",  id="1_char"),
    P("012", 1, 3, "012",  id="scrolling_limited_to_actual_offset"),
    P("012\n345", 3, 1, "2\n345",  id="scrolling_pushes_newline_at_edge"),
    P("012\n345", 2, 1, "12\n345",  id="scrolling_pushes_displayed_newline"),
    P("01234567890", 2, 2, "012345678",  id="scrolling_pushes_text_off_widget_single_line"),
    P("0\n1\n2\n3\n4\n5", 2, 1, "1\n2\n3\n",  id="scrolling_pushes_text_off_widget_multiple_lines"),
])
def test_softlines_scroll_characters_right(text, initial_offset, nchars, expected_displayed):

    sh = TM.shape((3,3))
    sl = TM.widgets.text.SoftLines(sh.text[1], text, max_text_size=20, offset=initial_offset)
    sl.scroll_char_right(nchars)
    assert sl.value == text
    assert sl.displayed_value == expected_displayed


@pytest.mark.parametrize(["text", "offset", "nlines", "expected_displayed"],  [
    P("012",0, 1, "012",  id="1_line_no_buffer"),
    P("012",1, 1, "012",  id="1_line_single_char_in_buffer"),
    P("012\n345", 3, 1, "012\n345",  id="1_lines_scroll_down"),
    P("012\n345\n", 3, 1, "012\n345\n",  id="1_lines_scroll_down_lf"),
    P("012\n345\n678\n901\n234", 9, 2, "345\n678\n901\n",  id="2_lines_scroll_down_text_goes_off_screen"),
    P("012345678", 6, 1, "345678",  id="1_physical_line_no_line_breaks"),
])

def test_softlines_scroll_lines_down(text, offset, nlines, expected_displayed):
    sh = TM.shape((3,3))
    sl = TM.widgets.text.SoftLines(sh.text[1], text, offset=offset, max_text_size=20)
    sl.scroll_line_down(nlines)
    assert sl.value == text
    assert sl.displayed_value == expected_displayed

@pytest.mark.parametrize(["text", "nlines", "expected_displayed"],  [
    P("012", 1, "",  id="1_line"),
    P("012\n345", 1, "345",  id="1_lines_scroll_up"),
    P("012\n345\n789", 1, "345\n789",  id="2_lines_scroll_up"),
    P("012\n345\n", 1, "345\n",  id="1_line_new_line_at_end"),
    P("012345", 1, "345",  id="1_line_from_spam_of_2"),
    P("012\n345", 1, "345",  id="1_line_of_2"),
    P("0123\n456789012", 1, "3\n456789", id="1_line_from_spam_of_2_scroll_bottom_long_line_up")
])
def test_softlines_scroll_lines_up(text, nlines, expected_displayed):
    sh = TM.shape((3,3))
    sl = TM.widgets.text.SoftLines(sh.text[1], text, max_text_size=20)
    sl.scroll_line_up(nlines)
    assert sl.value == text
    assert sl.displayed_value == expected_displayed

