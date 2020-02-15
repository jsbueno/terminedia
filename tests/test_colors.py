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

def test_color_by_hex6_works():
    c = Color("red")
    assert tuple(c.components) == (255, 0, 0)
    assert c.normalized == (1.0, 0, 0)
