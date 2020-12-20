import inspect
from inspect import signature

import pytest

from terminedia import Color

from terminedia.utils import combine_signatures, TaggedDict, HookList
from terminedia.utils.descriptors import ObservableProperty
from terminedia.utils import Rect, V2, Gradient, EPSILON


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
    x = TaggedDict()
    assert not x


def test_tagged_dictionary_can_contain_simple_items():
    x = TaggedDict()
    x["simple"] = "simple"

    assert x["simple"] == ["simple"]

def test_tagged_dictionary_can_delete_simple_items():
    x = TaggedDict()
    x["simple"] = "simple"
    del x["simple"]

    with pytest.raises(KeyError):
        x["simple"]


def test_tagged_dictionary_can_contain_items_with_2_tags():
    x = TaggedDict()
    x["first", "second"] = "element"

    assert x["first"] == ["element"]
    assert x["second"] == ["element"]


def test_tagged_dictionary_can_delete_itens_by_any_tag():
    x = TaggedDict()
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
    x = TaggedDict()
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
    x = TaggedDict()
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
    x = TaggedDict()
    y = x.view("animals")

    h = y.add("dog")

    assert h
    assert y[()] == ["dog"]
    assert x[()] == ["dog"]

    assert h in x
    del x[h]
    assert not x

def test_tagged_dictionary_views_add_method_unique_handles():
    x = TaggedDict()
    y = x.view("animals")

    h1 = y.add("dog")
    h2 = y.add("cat")

    assert h1 != h2


def test_tagged_dictionary_views_can_remove_by_value():
    x = TaggedDict()
    y = x.view("animals")

    h1 = y.add("dog")

    y.remove("dog")
    assert not y

    with pytest.raises(ValueError):
        y.remove("dog")

def test_hook_list_compares_eq_ok():
    from copy import copy
    a = HookList([1,2,3])
    b = HookList([1,2,3])

    assert a == b
    b.append(4)
    assert a != b
    b.pop()
    b[0] = 0
    assert a != b


def test_hook_list_shallow_copy_yields_a_copy():
    from copy import copy
    a = HookList([1,2,3])
    b = copy(a)
    c = a.copy()

    assert a == b
    assert a == c

    a.append(4)
    assert a != b
    assert a != c


def test_hook_list_shallow_copy_dont_trigger_side_effects():

    class DoubleList(HookList):
        def insert_hook(self, item):
            return 2 * item

    a = DoubleList([1,2,3])
    c = a.copy()

    assert a == c



def test_observable_property_works_for_write_event():

    class A:
        b = ObservableProperty()

    flag = False
    def callback(*args):
        nonlocal flag
        flag = True

    a = A()
    A.b.register(a, "set", callback)

    assert not flag
    a.b = None
    assert flag


def test_observable_property_works_for_get_event():

    class A:
        b = ObservableProperty()

    flag = False
    def callback(*args):
        nonlocal flag
        flag = True

    a = A()
    a.b = None

    getattr(a, "b", None)
    assert not flag
    A.b.register(a, "get", callback)
    getattr(a, "b", None)
    assert flag

def test_observable_property_works_for_del_event():

    class A:
        b = ObservableProperty()

    flag = False
    def callback(*args):
        nonlocal flag
        flag = True

    a = A()

    A.b.register(a, "del", callback)

    a.b = None
    getattr(a, "b", None)
    assert not flag
    del a.b
    assert flag
    assert not hasattr(a, "b")



def test_observable_property_unregister_works():

    class A:
        b = ObservableProperty()

    flag = False
    def callback(*args):
        nonlocal flag
        flag = True

    a = A()
    handler = A.b.register(a, "set", callback)
    a.b = None
    assert flag
    flag = None
    assert A.b.unregister(handler)
    a.b = None
    assert not flag
    assert not A.b.unregister(handler)


def test_observable_property_deleting_instance_clears_handlers():

    class A:
        b = ObservableProperty()

    flag = False
    def callback(*args):
        nonlocal flag
        flag = True

    a = A()
    handler = A.b.register(a, "set", callback)
    assert A.b.registry[a]
    assert A.b.callbacks[handler]
    del a
    assert len(A.b.registry) == 0
    assert handler not in A.b.callbacks


def test_observable_property_handlers_change_and_several_callbacks_happen():

    class A:
        b = ObservableProperty()

    counter = 0
    def callback(*args):
        nonlocal counter
        counter += 1

    a = A()
    handler1 = A.b.register(a, "set", callback)
    handler2 = A.b.register(a, "set", callback)
    assert handler1 != handler2

    a.b = None
    assert counter == 2


def test_observable_property_works_for_as_property_decorator():

    class A:
        @ObservableProperty
        def b(self):
            return self._b

        @b.setter
        def b(self, value):
            self._b = value

        @b.deleter
        def b(self):
            del self._b

    flag = False
    def callback(*args):
        nonlocal flag
        flag = True

    a = A()
    A.b.register(a, "set", callback)

    a.b = None

    assert a.b is None
    del a.b
    with pytest.raises(AttributeError):
        a.b

    assert flag


def test_observable_property_works_for_class_registers():

    class A:
        b = ObservableProperty()

    flag = False
    def callback(instance, value=None):
        nonlocal flag
        flag = True

    a1 = A()
    a2 = A()
    A.b.register(None, "set", callback)
    a1.b = 5
    assert flag
    flag = False
    a2.b = 23
    assert flag


def test_observable_property_for_class_and_instances_is_independent():

    class A:
        b = ObservableProperty()

    flag1 = flag2 = flagcls = False

    def callbackcls(instance, value=None):
        nonlocal flagcls
        flagcls = True

    def callback1(instance, value=None):
        nonlocal flag1
        flag1 = True

    def callback2(instance, value=None):
        nonlocal flag2
        flag2 = True

    a1 = A()
    a2 = A()
    A.b.register(None, "set", callbackcls)
    A.b.register(a1, "set", callback1)
    A.b.register(a2, "set", callback2)
    a1.b = 5
    assert flag1 and flagcls and not flag2
    flagcls = False
    flag1 = False
    a2.b = 23
    assert not flag1 and flagcls and  flag2


def test_observable_property_for_subclasses_is_independent():

    class A:
        b = ObservableProperty()

    class B(A):
        pass

    flag1 = flag2 = flaguniversal = False

    def callbackuniversal(instance, value=None):
        nonlocal flaguniversal
        flaguniversal = True

    def callback1(instance, value=None):
        nonlocal flag1
        flag1 = True

    def callback2(instance, value=None):
        nonlocal flag2
        flag2 = True

    a1 = A()
    b2 = B()
    A.b.register(None, "set", callbackuniversal)
    A.b.register(A, "set", callback1)
    B.b.register(B, "set", callback2)
    a1.b = 5
    assert flag1 and not flag2 and flaguniversal
    flaguniversal = False
    flag1 = False
    b2.b = 23
    assert not flag1 and flag2 and flaguniversal


@pytest.mark.parametrize(
    ["args", "kwargs"],[
        [[(10, 10), (20, 20)], {}],
        [[[10, 10], [20, 20]], {}],
        [[V2(10, 10), V2(20, 20)], {}],
        [[[10, 10, 20, 20]], {}],
        [[(10, 10, 20, 20)], {}],
        [[10, 10, 20, 20], {}],
        [Rect((10, 10), (20, 20)), {}],
        [[Rect((10, 10), (20, 20))], {}],
        [[], {"left_or_corner1": (10, 10), "top_or_corner2": (20, 20)}],
        [[(10, 10)], {"width_height": (10, 10)}],
        [[(10, 10)], {"width": 10, "height": 10}],
        [[(10, 10)], {"right": 20, "bottom": 20}],
        [[(10, 10)], {"center": (15, 15)}],
        [[], {"right": 10, "bottom": 10, "center": (15, 15)}],
])
def test_rect_constructor(args, kwargs):
    r = Rect(*args, **kwargs)
    assert r == Rect((10, 10), (20, 20))


@pytest.mark.parametrize(
    ["args", "kwargs", "expected"],[
        [[(10, 10), (20, 20)], {}, (10, 10, 20, 20)],
        [[], {}, (0, 0, 0, 0)],
        [[(10, 10)], {}, (0, 0, 10, 10)],
])
def test_rect_constructor_with_expected_result(args, kwargs, expected):
    r = Rect(*args, **kwargs)
    assert r == Rect(*expected)
