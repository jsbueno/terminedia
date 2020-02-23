import pytest
import terminedia.image as IMG
import terminedia as TM
from terminedia.values import DEFAULT_FG, Directions as D

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

