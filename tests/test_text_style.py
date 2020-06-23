import terminedia as TM
from terminedia.text.style import StyledSequence, Mark

import pytest

from conftest import rendering_test, fast_and_slow_render_mark

@pytest.mark.fixture
def styled_text():
    sc = TM.Screen((20, 10))
    sh = TM.shape((20, 10))
    sp1 = sc.data.sprites.add(sh)
    text_plane = sh.text[1]
    return sc, sh, text_plane


@pytest.mark.parametrize(*fast_and_slow_render_mark)
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
@pytest.mark.parametrize(*fast_and_slow_render_mark)
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
@pytest.mark.parametrize(*fast_and_slow_render_mark)
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
@pytest.mark.parametrize(*fast_and_slow_render_mark)
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


@pytest.mark.parametrize(
    ("attrname", "value", "attr2", "value2"), [
        ("color", TM.Color("red"), "background", TM.Color("white")),
])
@pytest.mark.parametrize(*fast_and_slow_render_mark)
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

