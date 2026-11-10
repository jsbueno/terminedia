import inspect
from inspect import signature

import pytest

from terminedia import Color

from terminedia.utils import combine_signatures, TaggedDict, HookList
from terminedia.utils.descriptors import ObservableProperty
from terminedia.utils import Rect, V2, ColorGradient, HSVColorGradient, Gradient, EPSILON
from terminedia.utils.gradient import _unit_stops, _interpolate_hue


def test_gradient_works():
    gr = ColorGradient([(0, (0, 0, 0)), (1, (1, 1, 1,))])

    assert isinstance(gr[0], Color)
    assert gr[0] == Color((0, 0, 0))
    assert gr[1] == Color((1, 1, 1))
    assert gr[.5] == Color((0.5, 0.5, 0.5))


def test_gradient_works_with_implicit_stops():
    gr = ColorGradient([(0, 0, 0), (1, 1, 1)])

    assert isinstance(gr[0], Color)
    assert gr[0] == Color((0, 0, 0))
    assert gr[1] == Color((1, 1, 1))
    assert gr[.5] == Color((0.5, 0.5, 0.5))

    gr = ColorGradient([(0, 0, 0), (1, 1, 1), (255, 0, 0)])

    assert isinstance(gr[0], Color)
    assert gr[0] == Color((0, 0, 0))
    assert gr[0.5] == Color((255, 255, 255))
    assert gr[1.0] == Color((255, 0, 0))


def test_gradient_with_single_stop_works_after_stop():
    gr = ColorGradient([(0, (255, 0, 0)) ])
    assert gr[0] == Color((255, 0, 0))
    assert gr[.5] == Color((255, 0, 0))
    assert gr[1] == Color((255, 0, 0))


def test_gradient_with_single_stop_works_before_stop():
    gr = ColorGradient([(.5, (255, 0, 0)) ])
    assert gr[0] == Color((255, 0, 0))
    assert gr[.5] == Color((255, 0, 0))
    assert gr[1] == Color((255, 0, 0))


def test_gradient_can_be_updated_with_new_points():
    gr = ColorGradient([(0, (0, 0, 0)), (1, (1, 1, 1,))])

    assert gr[.5] == Color((0.5, 0.5, 0.5))
    gr[.5] = (0, 255, 0)

    assert gr[.5] == Color((0, 255, 0))
    assert gr[.25] == Color((0, .5, 0))


def test_gradient_update_after_last_stop_works():
    gr = ColorGradient([(.5, (255, 0, 0))])

    gr[.7] = (0, 255, 0)

    assert gr[0] == Color((255, 0, 0))
    assert gr[.5] == Color((255, 0, 0))
    assert gr[.7] == Color((0, 255, 0))
    assert gr[1] == Color((0, 255, 0))
    assert gr[.6] == Color((.5, .5, 0))


def test_gradient_update_before_first_stop_works():
    gr = ColorGradient([(.5, (255, 0, 0))])

    gr[.3] = (0, 255, 0)

    assert gr[1] == Color((255, 0, 0))
    assert gr[.5] == Color((255, 0, 0))
    assert gr[.3] == Color((0, 255, 0))
    assert gr[0] == Color((0, 255, 0))
    assert gr[.4] == Color((.5, .5, 0))


def test_gradient_can_be_updated_replacing_points():
    # Todo: add an "add_stop" method
    gr = ColorGradient([(0, (0, 0, 0)), (1, (1, 1, 1,))])

    assert gr[.5] == Color((0.5, 0.5, 0.5))
    gr[.5] = (0, 255, 0)

    assert gr[.5] == Color((0, 255, 0))
    gr[.5] = (255, 0, 0)

    assert gr[.5] == Color((255, 0, 0))
    assert gr[.25] == Color((.5, 0, 0))


def test_gradient_can_be_updated_with_point_just_before():
    # Todo: add an "add_stop" method
    gr = ColorGradient([(0, (0, 0, 0)), (1, (1, 1, 1,))])

    assert gr[.5] == Color((0.5, 0.5, 0.5))
    gr[.5] = (0, 255, 0)

    gr[.5 - EPSILON] = (255, 0, 0)

    assert gr[.5] == Color((0, 255, 0))
    assert gr[.4999] == Color((254, 0, 0))


def test_gradient_can_be_updated_with_point_just_after():
    # Todo: add an "add_stop" method
    gr = ColorGradient([(0, (0, 0, 0)), (1, (1, 1, 1,))])

    assert gr[.5] == Color((0.5, 0.5, 0.5))
    gr[.5] = (0, 255, 0)

    gr[.5 + EPSILON] = (255, 0, 0)

    assert gr[.5] == Color((0, 255, 0))
    assert gr[.4999] == Color((0, 254, 0))
    assert gr[.50001] == Color((255, 0, 0))


def test_gradient_scalling_works():
    gr = ColorGradient([(0, (0, 0, 0)), (1, (1, 1, 1,))])
    gr_10 = gr.scale(10)
    gr_100 = gr.scale(100)

    assert gr_10[0] == Color((0, 0, 0))
    assert gr_10[10] == Color((1, 1, 1))
    assert gr_10[5] == Color((0.5, 0.5, 0.5))
    assert gr[1] == Color((1, 1, 1))
    assert gr_10.parent is gr

    assert gr_100[0] == Color((0, 0, 0))
    assert gr_100[100] == Color((1, 1, 1))
    assert gr_100[50] == Color((0.5, 0.5, 0.5))
    assert gr_100.parent is gr


def test_gradient_scaled_can_set_new_color():
    gr = ColorGradient([(0, (0, 0, 0)), (1, (1, 1, 1,))])
    gr_10 = gr.scale(10)
    gr_10[5] = (255, 0, 0)

    assert gr[0.5] == Color((255, 0, 0))

def test_gradient_root_attribute_works():
    gr = ColorGradient ([(0, "red"  ), (1, "green" )])
    gr2 = gr.scale(10)
    gr3 = gr2.scale(10)
    assert gr.root is gr
    assert gr2.root is gr
    assert gr3.root is gr

def test_gradient_scale_works_in_already_scaled_gradients():
    gr = ColorGradient ([(0, "red"), (1, "green")])
    gr2 = gr.scale(10)
    gr3 = gr2.scale(10)
    assert gr3.scale_factor == 100


def test__unit_stops():
    assert list(_unit_stops(2)) == [0, 1]
    assert list(_unit_stops(3)) == [0, .5, 1]
    assert list(_unit_stops(5)) == [0, .25, .5, .75, 1]


def test_interpolate_hue_takes_shortest_path():
    assert _interpolate_hue(0.0, 0.75, 0.5) == pytest.approx(0.875)
    assert _interpolate_hue(0.75, 0.0, 0.5) == pytest.approx(0.875)


def test_hsv_color_gradient_matches_rgb_for_gray_scale():
    gr_rgb = ColorGradient([(0, (0, 0, 0)), (1, (1, 1, 1))])
    gr_hsv = HSVColorGradient([(0, (0, 0, 0)), (1, (1, 1, 1))])
    for position in (0, 0.25, 0.5, 0.75, 1):
        assert gr_hsv[position].isclose(gr_rgb[position], abs_tol=1)


def test_hsv_color_gradient_differs_from_rgb_for_hue_change():
    gr_rgb = ColorGradient([(0, "red"), (1, "blue")])
    gr_hsv = HSVColorGradient([(0, "red"), (1, "blue")])
    assert gr_rgb[0.5] != gr_hsv[0.5]
    h_red = Color("red").hsv[0]
    h_blue = Color("blue").hsv[0]
    expected = Color(hsv=(_interpolate_hue(h_red, h_blue, 0.5), 1, 1))
    assert gr_hsv[0.5].isclose(expected, abs_tol=2)
