import inspect
from inspect import signature

import pytest

from terminedia.utils import Color

def test_color_by_name_works():
    c = Color("red")
    assert "red" in repr(c)
    assert tuple(c.components) == (255, 0, 0)

def test_color_by_int_works():
    c = Color((255, 0, 0))
    assert tuple(c.components) == (255, 0, 0)

def test_color_by_float_works():
    c = Color((1.0, 0, 0))
    assert tuple(c.components) == (255, 0, 0)

def test_color_by_hex3_works():
    c = Color("#f00")
    assert tuple(c.components) == (255, 0, 0)
    c = Color("#F00")
    assert tuple(c.components) == (255, 0, 0)

def test_color_by_hex6_works():
    c = Color("#ff0000")
    assert tuple(c.components) == (255, 0, 0)
    c = Color("#FF0000")
    assert tuple(c.components) == (255, 0, 0)

def test_color_by_hsv_works():
    c = Color(hsv=(0, 1, 1))
    assert tuple(c.components) == (255, 0, 0)

def test_normalized_color_works():
    c = Color("red")
    assert tuple(c.components) == (255, 0, 0)
    assert c.normalized == (1.0, 0, 0)

def test_can_get_color_component_by_name():
    c = Color("red")
    assert c.red == 255 and c.green == 0 and c.blue == 0

def test_can_set_color_component_by_name():
    c = Color("red")
    c.green = 255
    assert c.components == (255, 255, 0)
    c = Color("red")
    c.green = 1.0
    assert c.components == (255, 255, 0)

def test_color_name_is_reset_on_any_change():
    c = Color("red")
    assert c.name == "red"
    c.green = 255
    assert not c.name
    c = Color("red")
    c[1] = 1.0
    assert not c.name
    c = Color("red")
    c.components = (0,1,0)
    assert not c.name

def test_can_set_color_component_by_index():
    c = Color("red")
    c[1] = 255
    assert c.components == (255, 255, 0)

def test_can_sub_colors():
    c = Color("red")
    c -= Color((255, 0, 0))
    assert c.components == (0, 0, 0)


def test_subtracting_colors_dont_underflow():
    c = Color((200, 0, 0))
    c -= Color((255, 255, 0))
    assert c.components == (0, 0, 0)

def test_can_add_colors():
    c = Color("red")
    c += Color((0, 255, 0))
    assert c.components == (255, 255, 0)

def test_can_add_colors_to_sequences():
    c = Color("red")
    c += [0, 1.0, 0]
    assert c.components == (255, 255, 0)

def test_adding_colors_dont_overflow():
    c = Color((200, 0, 0))
    c += Color((200, 255, 0))
    assert c.components == (255, 255, 0)

def test_html_rendering_of_color():
    c = Color((255, 128, 0))
    assert c.html == "#FF8000"

def test_setting_hsv_component_works():
    c1 = Color("red")
    c1.hue = 0.5

    assert c1.components == (0, 255, 255)
    c1 = Color("red")
    c1.saturation = 0.5

    assert c1.components == (255, 127, 127)

def test_colors_isclose():
    a = Color("black")
    assert a.isclose((0, 2, 2))
    assert not a.isclose((0, 2, 4))
    assert a.isclose((0, 2, 4), abs_tol=10)
