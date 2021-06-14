import string

import pytest
import terminedia.image as IMG
import terminedia as TM
from terminedia.values import DEFAULT_FG, Directions as D
from terminedia.transformers import GradientTransformer

from conftest import rendering_test, fast_render_mark

Color = TM.Color


def test_transformer_character_channel_works_with_static_transform():
    sh = TM.shape((1,1))
    sh[0,0] = "*"
    assert sh[0,0].value == "*"
    sh.context.transformers.append(TM.Transformer(char="."))
    assert sh[0,0].value == "."

def test_transformer_character_channel_works():
    sh = TM.shape((1,1))
    sh[0,0] = "*"
    assert sh[0,0].value == "*"
    sh.context.transformers.append(TM.Transformer(char=lambda value: "."))
    assert sh[0,0].value == "."


def test_transformer_foreground_channel_works():
    sh = TM.shape((1,1))
    sh.context.color = "red"
    sh[0,0] = "*"
    assert sh[0,0].foreground == Color("red")
    sh.context.transformers.append(TM.Transformer(foreground=lambda value: TM.Color((value.green, value.blue, value.red))))
    assert sh[0,0].value == "*"
    assert sh[0,0].foreground == Color("blue")


def test_transformer_background_channel_works():
    sh = TM.shape((1,1))
    sh.context.background = "red"
    sh[0,0] = "*"
    assert sh[0,0].background == Color("red")
    sh.context.transformers.append(TM.Transformer(background=lambda value: TM.Color((value.green, value.blue, value.red))))
    assert sh[0,0].value == "*"
    assert sh[0,0].background == Color("blue")


def test_transformer_effects_channel_works():
    sh = TM.shape((1,1))
    sh.context.effects = TM.Effects.underline
    sh[0,0] = "*"
    assert sh[0,0].effects == TM.Effects.underline
    sh.context.transformers.append(TM.Transformer(effects=lambda value: value | TM.Effects.blink))
    assert sh[0,0].value == "*"
    assert sh[0,0].effects == TM.Effects.blink | TM.Effects.underline


def test_transformers_can_be_stacked():
    sh = TM.shape((1,1))
    green = Color((0, 255, 0))
    sh.context.color = "red"
    sh.context.background = green
    sh.context.effects = TM.Effects.underline
    sh[0,0] = "*"
    res = tuple(sh[0,0])
    # in SVG land, from where we get the color names, 'green' is 0, 128, 0.
    green = Color((0, 255, 0))
    assert res == ("*", Color("red"), green, TM.Effects.underline)

    sh.context.transformers.append(TM.Transformer(char=lambda value: "."))
    res = tuple(sh[0,0])
    assert res == (".", Color("red"), green, TM.Effects.underline)

    sh.context.transformers.append(TM.Transformer(foreground=lambda value: TM.Color((value.green, value.blue, value.red))))
    res = tuple(sh[0,0])
    assert res == (".", Color("blue"), green, TM.Effects.underline)

    sh.context.transformers.append(TM.Transformer(background=lambda value: TM.Color((value.green, value.blue, value.red))))
    res = tuple(sh[0,0])
    assert res == (".", Color("blue"), Color("red"), TM.Effects.underline)

    sh.context.transformers.append(TM.Transformer(effects=lambda value: value | TM.Effects.blink))
    res = tuple(sh[0,0])
    assert res == (".", Color("blue"), Color("red"), TM.Effects.underline | TM.Effects.blink)


def test_transformers_stacked_are_run_in_order():
    sh = TM.shape((1,1))
    sh.context.color = "red"
    sh.context.background = "green"
    sh.context.effects = TM.Effects.underline
    sh[0,0] = "*"
    sh.context.transformers.append(TM.Transformer(char=lambda value: "."))
    sh.context.transformers.append(TM.Transformer(char=lambda value: "-" if value == "." else value))
    assert sh[0,0].value == "-"


def test_transformers_stack_accepts_insertions():
    sh = TM.shape((1,1))
    sh.context.color = "red"
    sh.context.background = "green"
    sh.context.effects = TM.Effects.underline
    sh[0,0] = "*"
    sh.context.transformers.append(TM.Transformer(char=lambda value: "-" if value == "." else "#"))
    assert sh[0,0].value == "#"
    sh.context.transformers.insert(0, TM.Transformer(char=lambda value: "."))
    assert sh[0,0].value == "-"


def test_transformer_dependency_injection_pixel_parameter():
    sh = TM.shape((1,1))
    sh[0,0] = "a"
    sh.context.transformers.append(TM.Transformer(effects=lambda pixel: TM.Effects.underline if pixel.value.isupper() else TM.Effects.none))
    assert sh[0,0].effects == TM.Effects.none
    sh[0,0] = "A"
    assert sh[0,0].effects == TM.Effects.underline


def test_transform_pixel_channel_works():
    sh = TM.shape((1,1))
    def new_pixel(value):
        return "*", TM.Color("red"), TM.Color("blue"), TM.Effects.underline

    sh.context.transformers.append(TM.Transformer(pixel=new_pixel, background=TM.Color("green")))
    assert tuple(sh[0,0]) == ("*", TM.Color("red"), TM.Color("green"), TM.Effects.underline)



# Test injection for "pos" parameter -

def test_transformers_container_bake_method_for_source_consuming_transformers():
    sh = TM.shape((5,5))
    sh.draw.set((2,2))
    reference_shape = TM.shape((5,5))
    # Emulates Dilate filter -
    for point in [(2,2), (2, 1), (1, 2), (3, 2), (2, 3)]:
        reference_shape.draw.set(point)

    TM.TransformersContainer([TM.transformers.library.Dilate]).bake(sh)

    joiner = lambda sh: [sh[pos].value for pos in TM.Rect(sh.size)]
    assert joiner(sh) == joiner(reference_shape)

## GradientTransformer tests

def screen_shape_sprite():
    sc = TM.Screen((26, 10))
    sh = TM.shape((26, 10))
    sp1 = sc.data.sprites.add(sh)
    gr = TM.ColorGradient([(0, (0,0,0)), (1, (1,1,1))])
    return sc, sh, sp1, gr


@pytest.mark.parametrize(*fast_render_mark)
@rendering_test
def test_gradient_transformer_works():
    sc, sh, sp, gr = screen_shape_sprite()
    tr = GradientTransformer(gr)
    sp.transformers.append(tr)
    sh.draw.line((0,5), (26, 5))
    sc.update()
    yield None
    assert sc.data[0,5].foreground == Color((0, 0, 0))
    assert sc.data[12,5].foreground.isclose(Color((.5, .5, .5)), abs_tol=10)
    assert sc.data[25,5].foreground == Color((255, 255, 255))


@pytest.mark.parametrize(*fast_render_mark)
@rendering_test
def test_gradient_transformer_works_with_background_channel():
    sc, sh, sp, gr = screen_shape_sprite()
    tr = GradientTransformer(gr, channel="background")
    sp.transformers.append(tr)
    sh.draw.line((0,5), (26, 5), char="*", color=(255, 0, 0))
    sc.update()
    yield None
    assert sc.data[0,5].foreground == Color((255, 0, 0))
    assert sc.data[0,5].background == Color((0, 0, 0))
    assert sc.data[12,5].background.isclose(Color((.5, .5, .5)), abs_tol=10)
    assert sc.data[25,5].background == Color((255, 255, 255))


# TODO: test for other channels than "background" require a custom gradient
# object, that will return a variation of characters according to the position


@pytest.mark.parametrize(*fast_render_mark)
@rendering_test
def test_gradient_transformer_works_with_text_channel():
    sc, sh, sp, gr = screen_shape_sprite()

    class CharGradient:
        def __getitem__(self, pos):
            pos = int(pos * 25)
            return string.ascii_uppercase[pos]

    tr = GradientTransformer(CharGradient(), channel="char")

    sp.transformers.append(tr)
    sh.draw.line((0,5), (26, 5), char="*", color=(255, 0, 0))
    sc.update()
    yield None
    assert sc.data[0,5].foreground == Color((255, 0, 0))
    assert sc.data[0,5].value == "A"
    assert sc.data[12,5].value == "M"
    assert sc.data[25,5].value == "Z"


@pytest.mark.parametrize(*fast_render_mark)
@rendering_test
def test_gradient_transformer_works_on_vertical_direction():
    sc, sh, sp, gr = screen_shape_sprite()
    tr = GradientTransformer(gr, direction=TM.Directions.DOWN)
    sp.transformers.append(tr)
    sh.draw.line((12,0), (12, 10))
    sc.update()
    yield None
    assert sc.data[12,0].foreground == Color((0, 0, 0))
    assert sc.data[12,5].foreground.isclose(Color((.5, .5, .5)), abs_tol=15)
    assert sc.data[12,9].foreground == Color((255, 255, 255))


@pytest.mark.parametrize(*fast_render_mark)
@rendering_test
def test_gradient_transformer_with_horizontal_size():
    sc, sh, sp, gr = screen_shape_sprite()
    tr = GradientTransformer(gr, size=10)
    sp.transformers.append(tr)
    sh.draw.line((0,5), (26, 5))
    sc.update()
    yield None
    assert sc.data[0, 5].foreground == Color((0, 0, 0))
    assert sc.data[5, 5].foreground.isclose(Color((.5, .5, .5)), abs_tol=15)
    assert sc.data[9,5].foreground == Color((255, 255, 255))
    assert sc.data[10,5].foreground == Color((0, 0, 0))
    assert sc.data[19, 5].foreground == Color((255, 255, 255))
    assert sc.data[20,5].foreground == Color((0, 0, 0))


@pytest.mark.parametrize(*fast_render_mark)
@rendering_test
def test_gradient_transformer_with_horizontal_size_and_direction_left():
    sc, sh, sp, gr = screen_shape_sprite()
    tr = GradientTransformer(gr, direction=TM.Directions.LEFT, size=10)
    sp.transformers.append(tr)
    sh.draw.line((0,5), (26, 5))
    sc.update()
    yield None
    assert sc.data[0, 5].foreground == Color((255, 255, 255))
    assert sc.data[5, 5].foreground.isclose(Color((.5, .5, .5)), abs_tol=15)
    assert sc.data[9,5].foreground == Color((0, 0, 0))
    assert sc.data[10,5].foreground == Color((255, 255, 255))


@pytest.mark.parametrize(*fast_render_mark)
@rendering_test
def test_gradient_transformer_with_horizontal_size_with_repeat_none():
    sc, sh, sp, gr = screen_shape_sprite()
    tr = GradientTransformer(gr, size=10, repeat="none")
    sp.transformers.append(tr)
    sh.draw.line((0,5), (26, 5))
    sc.update()
    yield None
    assert sc.data[0, 5].foreground == Color((0, 0, 0))
    assert sc.data[5, 5].foreground.isclose(Color((.5, .5, .5)), abs_tol=15)
    assert sc.data[9,5].foreground == Color((255, 255, 255))
    assert sc.data[10,5].foreground == Color((255, 255, 255))
    assert sc.data[19, 5].foreground == Color((255, 255, 255))


@pytest.mark.parametrize(*fast_render_mark)
@rendering_test
def test_gradient_transformer_with_horizontal_size_with_repeat_none_and_offset():
    sc, sh, sp, gr = screen_shape_sprite()
    tr = GradientTransformer(gr, size=10, repeat="none", offset=5)
    sp.transformers.append(tr)
    sh.draw.line((0,5), (26, 5))
    sc.update()
    yield None
    assert sc.data[0, 5].foreground == Color((0, 0, 0))
    assert sc.data[4, 5].foreground == Color((0, 0, 0))
    assert sc.data[14,5].foreground == Color((255, 255, 255))
    assert sc.data[19, 5].foreground == Color((255, 255, 255))


@pytest.mark.parametrize(*fast_render_mark)
@rendering_test
def test_gradient_transformer_with_horizontal_size_and_repeat_triangle():
    sc, sh, sp, gr = screen_shape_sprite()
    tr = GradientTransformer(gr, size=10, repeat="triangle")
    sp.transformers.append(tr)
    sh.draw.line((0,5), (26, 5))
    sc.update()
    yield None
    assert sc.data[0, 5].foreground == Color((0, 0, 0))
    assert sc.data[5, 5].foreground.isclose(Color((.5, .5, .5)), abs_tol=15)
    assert sc.data[9,5].foreground == Color((255, 255, 255))
    assert sc.data[10,5].foreground == Color((255, 255, 255))
    assert sc.data[19, 5].foreground == Color((0, 0, 0))
    assert sc.data[25,5].foreground.isclose(Color((.5, .5, .5)), abs_tol=15)


def test_gradient_transformer_with_repeat_truncate_generates_wrapper_receiving_propper_channel():
    from inspect import signature

    sc, sh, sp, gr = screen_shape_sprite()
    tr = GradientTransformer(gr, size=10, repeat="truncate", channel="char")
    assert "char" in signature(tr.char).parameters


@pytest.mark.parametrize(*fast_render_mark)
@rendering_test
def test_gradient_transformer_with_horizontal_size_with_repeat_truncate_and_offset():
    sc, sh, sp, gr = screen_shape_sprite()
    tr = GradientTransformer(gr, size=10, repeat="truncate", offset=5)
    sp.transformers.append(tr)
    sh.draw.line((0,5), (26, 5), color="red")
    sc.update()
    yield None
    assert sc.data[0, 5].foreground == Color((255, 0, 0))
    assert sc.data[3, 5].foreground == Color((255, 0, 0))
    assert sc.data[5, 5].foreground == Color((0, 0, 0))
    assert sc.data[14,5].foreground == Color((255, 255, 255))
    assert sc.data[19, 5].foreground == Color((255, 0, 0))
