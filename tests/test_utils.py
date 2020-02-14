import inspect
from inspect import signature

import pytest

from terminedia.utils import combine_signatures

def test_combine_signatures_works():
    context = {}
    def add_color(func):
        @combine_signatures(func)
        def wrapper(*args, color=None, **kwargs):
            nonlocal context
            context["color"] = color
            return func(*args, **kwargs)
        return wrapper
    @add_color
    def line(p1, p2):
        assert p1 == (0, 0)
        assert p2 == (10,10)

    sig = signature(line)

    assert 'p1' in  sig.parameters
    assert 'p2' in sig.parameters
    assert 'color' in sig.parameters
    assert sig.parameters['color'].kind == inspect._ParameterKind.KEYWORD_ONLY

    line((0,0), p2=(10,10), color="red")
    assert context["color"] == "red"


