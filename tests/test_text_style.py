import random
from collections.abc import Sequence
import terminedia as TM
from terminedia.text.style import StyledSequence, Mark, MLTokenizer

import pytest

from conftest import rendering_test, fast_render_mark

@pytest.mark.fixture
def styled_text():
    sc = TM.Screen((20, 10))
    sh = TM.shape((20, 10))
    sp1 = sc.data.sprites.add(sh)
    text_plane = sh.text[1]
    return sc, sh, text_plane


@pytest.mark.parametrize(*fast_render_mark)
@rendering_test
def test_styled_sequence_is_rendered():
    sc, sh, text_plane = styled_text()
    msg = "Hello World!"
    aa = StyledSequence(msg, {}, text_plane)
    aa.render()
    sc.update()
    yield None
    for i, char in enumerate(msg):
        assert sc.data[i, 0].value == char

@pytest.mark.parametrize(
    ("attrname", "value"), [
        ("color", TM.Color("red"),),
        ("background", TM.Color("green"),),
        ("effects", TM.Effects.blink),
])
@pytest.mark.parametrize(*fast_render_mark)
@rendering_test
def test_styled_sequence_is_rendered_with_attribute(attrname, value):
    sc, sh, text_plane = styled_text()
    msg = "Hello World!"
    aa = StyledSequence(msg, {0: Mark(attributes={attrname: value})}, text_plane)
    aa.render()
    sc.update()
    yield None
    # TODO: these should be aliased in TM.Context class.
    if attrname == "color":
        attrname = "foreground"
    for i, char in enumerate(msg):
        assert getattr(sc.data[i, 0], attrname) == value


@pytest.mark.parametrize(
    ("attrname", "value", "position", "attr2", "value2"), [
        ("color", TM.Color("red"),5, "background", TM.Color("white")),
        ("color", TM.Color("blue"), 1, "effects", TM.Effects.underline),
        ("color", TM.Color("yellow"), 100, "effects", TM.Effects.blink),
])
@pytest.mark.parametrize(*fast_render_mark)
@rendering_test
def test_styled_sequence_adds_attributes_at_mark(attrname, value, position, attr2, value2):
    sc, sh, text_plane = styled_text()
    msg = "Hello World!"
    aa = StyledSequence(
        msg, {
            0: Mark(attributes={attrname: value}),
            position: Mark(attributes={attr2: value2})
        },
        text_plane
    )
    aa.render()
    sc.update()
    yield None
    # TODO: these should be aliased in TM.Context class.
    if attrname == "color":
        attrname = "foreground"
    for i, char in enumerate(msg):
        assert getattr(sc.data[i, 0], attrname) == value
        if i >= position:
            assert getattr(sc.data[i, 0], attr2) == value2
        else:
            assert getattr(sc.data[i, 0], attr2) != value2


@pytest.mark.parametrize(
    ("pos1", "attrname", "value", "pos2", "default"), [
        (0, "color", TM.Color("red"),5, TM.DEFAULT_FG),
        (2, "background", TM.Color("blue"),7, TM.DEFAULT_BG),
        (2, "effects", TM.Effects.blink, 50, TM.Effects.none),
])
@pytest.mark.parametrize(*fast_render_mark)
@rendering_test
def test_styled_sequence_pops_attributes(pos1, attrname, value, pos2, default):
    sc, sh, text_plane = styled_text()
    msg = "Hello World!"
    aa = StyledSequence(
        msg, {
            pos1: Mark(attributes={attrname: value}),
            pos2: Mark(pop_attributes={attrname: None})
        },
        text_plane
    )
    aa.render()
    sc.update()
    yield None
    # TODO: these should be aliased in TM.Context class.
    if attrname == "color":
        attrname = "foreground"
    for i, char in enumerate(msg):
        if pos1 <=  i < pos2:
            assert getattr(sc.data[i, 0], attrname) == value
        else:
            assert getattr(sc.data[i, 0], attrname) == default


@pytest.mark.parametrize(("method",),[("merged",),("sequence",)])
@pytest.mark.parametrize(
    ("moveto", "rmoveto", "expected_pos"), [
        ((0,1), None, (0,1)),
        ((5,1), None, (5,1)),
        (None, (0, 1), (5,1)),
        (None, (-2, 3), (3, 3)),
        ((10, 6), (-1, -1), (9, 5)),
])
@pytest.mark.parametrize(*fast_render_mark)
@rendering_test
def test_styled_sequence_move_and_relative_move_work(moveto, rmoveto, expected_pos, method):
    sc, sh, text_plane = styled_text()
    msg = "01234566789"
    if method == "merged":
        mark_seq = Mark(moveto=moveto, rmoveto=rmoveto)
    elif method == "sequence":
        mark_seq = [Mark(moveto=moveto), Mark(rmoveto=rmoveto)]

    # let's trhow in some color -
    r = random.Random(hash((moveto, rmoveto, method)))
    pos = r.randrange(0, 5)
    attr = r.choice(["color", "background"])
    color = r.choice(["yellow", "red", "green", "blue"])


    aa = StyledSequence(
        msg, {
            pos: Mark(attributes={attr: color}),
            5: mark_seq,
        },
        text_plane
    )
    aa.render()
    sc.update()
    yield None
    # TODO: these should be aliased in TM.Context class.
    assert sc.data[5,0].value == TM.values.EMPTY if expected_pos != (5,0) else True
    assert sc.data[expected_pos].value == '5'

@pytest.mark.parametrize(
    ("attrname", "value", "attr2", "value2"), [
        ("color", TM.Color("red"), "background", TM.Color("white")),
])
@pytest.mark.parametrize(*fast_render_mark)
@rendering_test
def test_styled_sequence_mark_objects_can_be_sequence(attrname, value, attr2, value2):
    sc, sh, text_plane = styled_text()
    msg = "Hello World!"
    aa = StyledSequence(
        msg, {
            0: [
                Mark(attributes={attrname: value}),
                Mark(attributes={attr2: value2})
        ]},
        text_plane
    )
    aa.render()
    sc.update()
    yield None
    # TODO: these should be aliased in TM.Context class.
    if attrname == "color":
        attrname = "foreground"
    for i, char in enumerate(msg):
        assert getattr(sc.data[i, 0], attrname) == value
        assert getattr(sc.data[i, 0], attr2) == value2


def test_mltokenizer_generates_marks():
    x = MLTokenizer("[color: blue]Hello World!")
    x.parse()
    assert x.parsed_text == "Hello World!"
    assert len(x.mark_sequence) == 1
    assert x.mark_sequence[0].attributes == {"color": TM.Color("blue")}


def test_mltokenizer_generates_mark_sequences_with_marksups_at_same_place():
    x = MLTokenizer("[color: blue][background: white]Hello World!")
    x.parse()
    assert x.parsed_text == "Hello World!"
    assert isinstance(x.mark_sequence[0], Sequence)
    assert len(x.mark_sequence[0]) == 2
    assert x.mark_sequence[0][0].attributes == {"color": TM.Color("blue")}
    assert x.mark_sequence[0][1].attributes == {"background": TM.Color("white")}


@pytest.mark.parametrize(*fast_render_mark)
@rendering_test
def test_styled_sequence_retrives_marks_from_text_plane():
    sc, sh, text_plane = styled_text()
    text_plane.marks[1,0] = Mark(attributes={"color": TM.Color("yellow")})
    msg = "Hello World!"
    aa = StyledSequence(
        msg, {},
        text_plane
    )
    aa.render()
    sc.update()
    yield None
    assert sc.data[0,0].foreground == TM.DEFAULT_FG
    for i, letter in enumerate(msg[1:],1):
        assert sc.data[i,0].foreground == TM.Color("yellow")


@pytest.mark.parametrize(*fast_render_mark)
@rendering_test
def test_text_wraps_at_text_plane_boundary():
    sc, sh, text_plane = styled_text()
    msg = "Hello World!"
    # Wrapping depends on Mark objects automatically
    # placed at the text_plane border to move
    # the rendering to the following line.
    text_plane[text_plane.width - 4, 5] = msg

    sc.update()
    yield None
    assert sc.data[text_plane.width -1, 5].value == "l"
    assert sc.data[0, 6].value == "o"
    assert sc.data[2, 6].value == "W"
    assert sc.data[text_plane.width, 5].value == " "
