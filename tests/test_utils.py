import inspect
from inspect import signature

import pytest

from terminedia.utils import combine_signatures, TaggedDictionary

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


def test_tagged_dictionary_is_created():
    x = TaggedDictionary()
    assert not x


def test_tagged_dictionary_can_contain_simple_items():
    x = TaggedDictionary()
    x["simple"] = "simple"

    assert x["simple"] == ["simple"]

def test_tagged_dictionary_can_delete_simple_items():
    x = TaggedDictionary()
    x["simple"] = "simple"
    del x["simple"]

    with pytest.raises(KeyError):
        x["simple"]


def test_tagged_dictionary_can_contain_items_with_2_tags():
    x = TaggedDictionary()
    x["first", "second"] = "element"

    assert x["first"] == ["element"]
    assert x["second"] == ["element"]


def test_tagged_dictionary_can_delete_itens_by_any_tag():
    x = TaggedDictionary()
    x["first", "second"] = "element"
    del x["first"]
    assert not x

    x["first", "second"] = "element"
    del x["second"]
    assert not x

    x["first", "second"] = "element"
    del x["second", "first"]
    assert not x

    x["first", "second"] = "element"
    with pytest.raises(KeyError):
        x["simple", "second", "third"]

    assert x


def test_tagged_dictionary_views_work():
    x = TaggedDictionary()
    y = x.view("animals")
    z = y.view("insects")

    z["0"] = "butterfly"
    z["1"] = "bee"
    assert len(z) == 2

    z1 = y.view("mammals")
    z1["0"] = "dog"

    w = x.view("things")
    w["0"] = "chair"

    assert len(z) == 2
    assert len(z1) == 1
    assert len(y) == 3

    assert len(w) == 1

    assert len(x) == 4

    assert set(x.values()) == {"chair", "dog", "bee", "butterfly"}
    assert set(x[()]) == {"chair", "dog", "bee", "butterfly"}


def test_tagged_dictionary_views_added_tag_reflects_on_other_tags():
    x = TaggedDictionary()
    y = x.view("animals")
    z = y.view("insects")
    z1 = y.view("mammals")

    assert not y

    z["mammals"] = "spyderman"

    assert y
    assert len(y) == 1
    assert len(z) == 1

    assert x["insects", "mammals"] == ["spyderman"]

def test_tagged_dictionary_views_add_method():
    x = TaggedDictionary()
    y = x.view("animals")

    h = y.add("dog")

    assert h
    assert y[()] == ["dog"]
    assert x[()] == ["dog"]

    assert h in x
    del x[h]
    assert not x

def test_tagged_dictionary_views_add_method_unique_handles():
    x = TaggedDictionary()
    y = x.view("animals")

    h1 = y.add("dog")
    h2 = y.add("cat")

    assert h1 != h2


def test_tagged_dictionary_views_can_remove_by_value():
    x = TaggedDictionary()
    y = x.view("animals")

    h1 = y.add("dog")

    y.remove("dog")
    assert not y

    with pytest.raises(ValueError):
        y.remove("dog")

