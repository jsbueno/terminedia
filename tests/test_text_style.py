import random
from collections.abc import Sequence
import terminedia as TM
from terminedia.text.style import StyledSequence, SpecialMark, Mark, MLTokenizer

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


def test_mltokenizer_generates_mark_sequences_with_markups_at_same_place():
    x = MLTokenizer("[color: blue][background: white]Hello World!")
    x.parse()
    assert x.parsed_text == "Hello World!"
    assert isinstance(x.mark_sequence[0], Sequence)
    assert len(x.mark_sequence[0]) == 2
    assert x.mark_sequence[0][0].attributes == {"color": TM.Color("blue")}
    assert x.mark_sequence[0][1].attributes == {"background": TM.Color("white")}

def test_mltokenizer_properly_accounts_transformers_spam():
    x = MLTokenizer("[transformer: Z][transformer: Y][transformer: X 20]1[/transformer]2[/transformer]")
    x.parse()
    assert x.mark_sequence[0][0].attributes == {"pretransformer": "Z"}
    assert x.mark_sequence[0][1].attributes == {"pretransformer": "Y 2"}
    assert x.mark_sequence[0][2].attributes == {"pretransformer": "X 20"}


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
def test_richtext_rendering_respects_existing_context():
    sc, sh, text_plane = styled_text()
    msg = "H[color: yellow]ell[/color]o World!"
    sh.context.color="red"
    text_plane[0, 0] = msg

    sc.update()
    yield None
    assert sc.data[0, 0].foreground == TM.Color("red")
    assert sc.data[1, 0].foreground == TM.Color("yellow")
    assert sc.data[4, 0].foreground == TM.Color("red")

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

@pytest.mark.parametrize(*fast_render_mark)
@rendering_test
def test_styled_sequence_can_handle_pretransformers():
    sc, sh, text_plane = styled_text()
    msg = "0123456789"
    tt = TM.Transformer(
        foreground=lambda pos: TM.Color((pos[0] * 25 % 256, 0, 0)),
        background=lambda pos: TM.Color((0, 0, (255 - pos[0] * 25) % 256)),
    )
    aa = StyledSequence(
        msg,{0: TM.Mark(attributes={"pretransformer": tt})} ,
        text_plane
    )
    aa.render()
    sc.update()
    yield None
    assert sc.data[0,0].foreground == TM.Color((0,0,0))
    assert sc.data[0,0].background == TM.Color((0,0,255))
    assert sc.data[9,0].foreground == TM.Color((225,0,0))
    assert sc.data[9,0].background == TM.Color((0,0,30))

@pytest.mark.parametrize(*fast_render_mark)
@rendering_test
def test_styled_sequence_retrieves_transformers_from_text_plane_transformers_map():
    sc, sh, text_plane = styled_text()
    text_plane.transformers_map["asteriscs"] = TM.Transformer(char="*")
    text_plane[0, 5] = "012[transformer: asteriscs]345[/transformer]6789"
    sc.update()
    yield None
    assert sc.data[2,5].value == "2"
    for i in range(3, 6):
        assert sc.data[i,5].value == "*"
    assert sc.data[6,5].value == "6"

def test_styled_text_anotates_writtings():
    sc, sh, text_plane = styled_text()
    msg = "Hello World!"
    # Special mark callable index uses dependency injection, like TM.Transformers.
    m = SpecialMark(index=lambda tick, length: tick % length, attributes={"color": TM.Color("red")})
    m1 = SpecialMark(index=lambda tick, length: (tick + 1) % length, pop_attributes={"color": None})

    # text_plane.marks.special.update(m, m1)
    mm = {"special": [m, m1]}

    aa = StyledSequence(
        msg, mark_sequence=mm,
        text_plane=text_plane,
        starting_point=(0, 5)
    )
    text_plane.render_styled_sequence(aa)

    # text_plane[0, 5] = msg

    assert text_plane.writtings
    assert text_plane.writtings_index
    assert text_plane.writtings[0] is aa


@pytest.mark.parametrize(*fast_render_mark)
@rendering_test
def test_styled_text_render_and_animate_special_marks():
    sc, sh, text_plane = styled_text()
    msg = "Hello World!"
    # Special mark callable index uses dependency injection, like TM.Transformers.
    m = SpecialMark(index=lambda tick, length: tick % length, attributes={"color": TM.Color("red")})
    m1 = SpecialMark(index=lambda tick, length: (tick + 1) % length, pop_attributes={"color": None})

    text_plane.marks.special.update([m, m1])

    text_plane[0, 5] = msg

    sc.update()
    yield None

    assert sc.data[0, 5].foreground == TM.Color("red")
    assert sc.data[1, 5].foreground == TM.values.DEFAULT_FG
    for i, char in enumerate(msg[:-1], 1):
        text_plane.update()
        sc.update()
        yield None
        assert sc.data[i - 1, 5].foreground == TM.values.DEFAULT_FG
        assert sc.data[i, 5].foreground == TM.Color("red")
        assert sc.data[i + 1, 5].foreground == TM.values.DEFAULT_FG
        assert sc.data[i + 2, 5].foreground == TM.values.DEFAULT_FG


# Inner unit testing for StyledSequence

def test_styled_text_push_context_attribute():
    seq = StyledSequence("", {})
    seq._enter_iteration()
    color = TM.Color("red")
    color2 = TM.Color("yellow")

    assert seq.context.color != color
    original = seq.context.color
    seq._context_push({"color": color}, {})
    assert seq.context.color == color
    seq._context_push({"color": color2}, {})
    assert seq.context.color == color2
    seq._context_push({}, {"color": None})
    assert seq.context.color == color
    seq._context_push({}, {"color": None})
    assert seq.context.color == original


def test_styled_text_push_context_sequence_attribute():
    from copy import copy
    seq = StyledSequence("", {})
    seq._enter_iteration()
    tr1 = TM.Transformer(foreground="red")
    tr2 = TM.Transformer(background="yellow")

    assert tr1 not in seq.context.pretransformers
    original = copy(seq.context.pretransformers)
    seq._context_push({"pretransformer": tr1}, {})
    assert seq.context.pretransformers[-1] == tr1
    seq._context_push({"pretransformer": tr2}, {})
    assert seq.context.pretransformers[-1] == tr2
    assert seq.context.pretransformers[-2] == tr1
    seq._context_push({}, {"pretransformer": None})
    assert seq.context.pretransformers[-1] == tr1
    seq._context_push({}, {"pretransformer": None})
    assert seq.context.pretransformers == original

