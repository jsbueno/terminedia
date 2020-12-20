import inspect
from inspect import signature

import pytest

from terminedia import Color

from terminedia.utils import combine_signatures, TaggedDict, HookList
from terminedia.utils.descriptors import ObservableProperty
from terminedia.utils import Rect, V2, ColorGradient, Gradient, EPSILON


def test_gradient_works():
    gr = ColorGradient([(0, (0, 0, 0)), (1, (1, 1, 1,))])

    assert isinstance(gr[0], Color)
    assert gr[0] == Color((0, 0, 0))
    assert gr[1] == Color((1, 1, 1))
    assert gr[.5] == Color((0.5, 0.5, 0.5))


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
