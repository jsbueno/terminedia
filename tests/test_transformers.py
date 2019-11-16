import pytest
import terminedia.image as IMG
import terminedia as TM
from terminedia.values import DEFAULT_FG, Directions as D

Color = TM.Color



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


# Test injection for "pos" parameter -
"""
TODO: write tests for the following features - and then code then down!
transformers also will accept a transformation matrix on the "spatial" channel for
positioning, scaling and rotating the original contents (the reverse transform
should fetch the orignal pixel with a nearest-neighbor search).
"Translating" can be implemented first, and would be enough for
integrating the Transformers branch.

A "source" channel, pointing an auxiliar shape that will override
the contents of the target shape, on read - (depending on
combination model - in the future a "behind" mode can be implemented.

The "combination mode" transformer parameter indicates how the pixels
in the other shape will be combined - at first only a  "normal" meaning override
the target pixel, with TM.Empty (space - char(0x20)) being "transparent" glyph,
and "TM.TRANSPARENT" on each of the foreground, background and effects channels
to prserve the respective channel on the target image.

 A couple of the SVG blend modes
may be implemented soon - https://www.w3.org/TR/compositing-1/#porterduffcompositingoperators
(per-channel operations on the auxiliar "source" shape shall be performed by
the transformers on that shape's context. Glyph will be overriden


"""
