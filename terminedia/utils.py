import inspect
import operator
import unicodedata
from collections.abc import MutableSequence
from functools import lru_cache, wraps, partial


def mirror_dict(dct):
    """Creates a new dictionary exchanging values for keys
    Args:
      - dct (mapping): Dictionary to be inverted
    """
    return {value: key for key, value in dct.items()}


class FrozenDict(dict):
    __slots__ = ()
    __setitem__ = None

    def __hash__(self):
        return hash(tuple(self.items()))


class V2(tuple):
    """2-component Vector class to ease drawing

    Works as a 2-sequence, but offers "x" and "y" properties to the coordinates
    as well as basic operations. As V2 inherits from Python's tuple, it is imutable
    and can be used as dictionary keys, among other common sequence operations.

    Args:
      x (number or 2-sequence): 1st vector coordinate or 2-sequence with coordinates
      y (number): 2nd vector coordinate. Ignored if x is a sequence
    Suported ops:
      - + (``__add__``): Adds both components of 2 vectors
      - - (``__sub__``): Subtracts both components of 2 vectors.
      - * (``__mul__``): Multiplies vector components by a scalar
      - abs (``__abs__``): Returns vector length
    """

    __slots__ = ()

    def __new__(cls, x=0, y=0):
        """Accepts two coordinates as two parameters for x and y"""
        # Enable working with values defined in Enums
        if hasattr(x, "value"):
            x = x.value
        if hasattr(x, "__len__") or hasattr(x, "__iter__"):
            x, y = x
        return super().__new__(cls, (x, y))

    def __init__(self, *args, **kw):
        # "Eat" subclass arguments that would
        # otherwise hit tuple.__init__ and
        # cause a fault.
        return
        # If composition of this class ever gets more complex, uncomment the
        # pedantic way to go is:

        # x, y = kw.pop(x, None), kw.pop(y, None)
        # if not x and not y and len(args) >= 2:
        # args = args[2:]
        # super().__init__(*args, **kw)

    x = property(lambda self: self[0])
    y = property(lambda self: self[1])

    def __add__(self, other):
        """Adds both components of a V2 or other 2-sequence"""
        return self.__class__(self[0] + other[0], self[1] + other[1])

    __radd__ = __add__

    def __sub__(self, other):
        """Subtracts both components of a V2 or other 2-sequence"""
        return self.__class__(self[0] - other[0], self[1] - other[1])

    def __rsub__(self, other):
        """Subtracts both components of a V2 or other 2-sequence"""
        return self.__class__(other[0] - self[0], other[1] - self[1])

    def __mul__(self, other):
        """multiplies a V2 by an scalar"""
        return self.__class__(self[0] * other, self[1] * other)

    def __truediv__(self, other):
        try:
            other = 1 / other
        except (ValueError, TypeError):
            return NotImplemented
        return self * other

    def __abs__(self):
        """Returns Vector length
           Returns:
             - (float): Euclidian length of vector

        """
        return (self.x ** 2 + self.y ** 2) ** 0.5

    @property
    def as_int(self):
        return self.__class__(int(self.x), int(self.y))

    def __repr__(self):
        return f"V2({self.x}, {self.y})"

    def max(self, other):
        return V2(max(self.x, other[0]), max(self.y, other[1]))

    def min(self, other):
        return V2(min(self.x, other[0]), min(self.y, other[1]))


class NamedV2(V2):
    """Vector meant to be used as constant, with a string-repr name"""

    def __init__(self, *args, name=None, **kw):
        """Optional name - if used as a descriptor, name is auto-set"""
        self.name = name
        super().__init__(*args, **kw)

    def __set_name__(self, owner, name):
        self.owner_name = owner.__name__
        self.name = name

    def __get__(self, instance, owner):
        return self

    def __repr__(self):
        return f"{self.owner_name}.{self.name}"

    def __str__(self):
        return self.name

    # Force operator methods to get these values as pure V2 instances
    # (so that adding "Directions" results in a normal vector,
    # not an object with a __dict__)
    for method in "__add__ __sub__ __mul__ __abs__ as_int".split():
        locals()[method] = (
            lambda method: lambda s, *args: getattr(V2, method)(V2(s), *args)
        )(method)

    @property
    def value(self):
        """Returns self, keeping compatibility with Python Enums if used as a descriptor"""
        return self


class Rect:
    __slots__ = ("_c1", "_c2")

    def __init__(
        self,
        left_or_corner1=None,
        top_or_corner2=None,
        right=None,
        bottom=None,
        *,
        width_height=None,
        width=None,
        height=None,
        center=None,
    ):
        if isinstance(left_or_corner1, Rect):
            self.c1 = left_or_corner1.c1
            self.c2 = left_or_corner1.c2
            return
        left = top = c1 = c2 = None
        if hasattr(left_or_corner1, "__len__"):
            if len(left_or_corner1) == 4:
                c1 = V2(left_or_corner1[:2])
                c2 = V2(left_or_corner1[2:])
            elif len(left_or_corner1) == 2:
                c1 = V2(left_or_corner1)
        elif isinstance(left_or_corner1, slice) or isinstance(top_or_corner2, slice):

            left = (
                left_or_corner1.start
                if isinstance(left_or_corner1, slice)
                else left_or_corner1
            )
            right = (
                left_or_corner1.stop
                if isinstance(left_or_corner1, slice)
                else left_or_corner1 + 1
            )
            top = (
                top_or_corner2.start
                if isinstance(top_or_corner2, slice)
                else top_or_corner2
            )
            bottom = (
                top_or_corner2.stop
                if isinstance(top_or_corner2, slice)
                else top_or_corner2 + 1
            )
        else:
            left = left_or_corner1

        if hasattr(top_or_corner2, "__len__") and len(top_or_corner2) == 2:
            c2 = V2(top_or_corner2)
        elif top is None:
            top = top_or_corner2

        if not width_height and width is not None and height is not None:
            width_height = width, height
        c1 =(
            c1
            if c1
            else (left, top)
            if left is not None and top is not None
            else (0, 0)
        )
        c2 =(
            c2
            if c2
            else (right, bottom)
            if right is not None and bottom is not None
            else (0, 0)
        )
        self.c1 = (min(c1[0], c2[0]), min(c1[1], c2[1]))
        self.c2 = (max(c1[0], c2[0]), max(c1[1], c2[1]))

        if width_height:
            self.width_height = width_height
        if center:
            self.center = center


    c1 = property(lambda s: s._c1)

    @c1.setter
    def c1(self, value):
        self._c1 = V2(value)

    c2 = property(lambda s: s._c2)

    @c2.setter
    def c2(self, value):
        self._c2 = V2(value)

    @property
    def width_height(self):
        return V2(self.width, self.height)

    @width_height.setter
    def width_height(self, value):
        self.width = value[0]
        self.height = value[1]

    @property
    def width(self):
        return self._c2.x - self._c1.x

    @width.setter
    def width(self, value):
        self._c2 = V2(self._c1.x + value, self._c2.y)

    @property
    def height(self):
        return self._c2.y - self._c1.y

    @height.setter
    def height(self, value):
        self._c2 = V2(self._c2.x, self._c1.y + value)

    @property
    def center(self):
        return (self._c1 + self._c2) * 0.5

    @center.setter
    def center(self, value):
        center = V2(value)
        w, h = self.width_height
        w2 = w / 2
        h2 = h / 2
        self._c1 = V2(center.x - w2, center.y - h2)
        self._c2 = V2(center.x + w2, center.y + h2)

    @property
    def left(self):
        return self._c1.x

    @left.setter
    def left(self, value):
        w = self.width
        self._c1 = V2(value, self._c1.y)
        self._c2 = V2(value + w, self._c2.y)

    @property
    def top(self):
        return self._c1.y

    @top.setter
    def top(self, value):
        h = self.height
        self._c1 = V2(self._c1.x, value)
        self._c2 = V2(self._c2.x, value + h)

    @property
    def right(self):
        return self._c2.x

    @right.setter
    def right(self, value):
        w = self.width
        self._c2 = V2(value, self._c2.y)
        self._c1 = V2(value - w, self._c1.y)

    @property
    def bottom(self):
        return self._c2.y

    @bottom.setter
    def bottom(self, value):
        h = self.height
        self._c2 = V2(self._c2.x, value)
        self._c1 = V2(self._c1.x, value - h)

    @property
    def as_int(self):
        return self.__class__(self._c1.as_int, self._c2.as_int)

    @property
    def area(self):
        return self.width * self.height

    def __eq__(self, other):
        if not isinstance(other, Rect):
            other = Rect(other)
        return other.c1 == self.c1 and other.c2 == self.c2

    def __contains__(self, other):
        """Verify if a point or rectangle is contained in 'self'.

        Python's convention of open-intervals on the upper boundaries applies:
        a point on the right or bottom values of the rectangle is not
        considered to be inside.
        """
        if isinstance(other, Rect):
            return other.c1 in self and other.c2 in self
        return self.left <= other[0] < self.right and self.top <= other[1] < self.bottom

    def collide(self, other):
        return (
            (other.top <= self.top <= other.bottom  or
             other.top <= self.bottom <= other.bottom or
             self.top <= other.top <= self.bottom
             ) and
            (other.left <= self.left <= other.right or
             other.left <= self.right <= other.right or
             self.left <= other.left <= self.right
             )
        )

    def __iter__(self):
        yield self.c1
        yield self.c2

    def __len__(self):
        return 4

    def __repr__(self):
        return f"{self.__class__.__name__}({tuple(self.c1)}, {tuple(self.c2)})"


class LazyBindProperty:
    """Special Internal Use Descriptor

    This creates the associated attribute in an instance only when the attribute is
    acessed for the first time, in a dynamic way. This allows objcts such as Shapes
    have specialized associated "draw", "high", "text", "sprites" attributes,
    and still be able to be created lightweight for short uses that will use just
    a few, or none, of these attributes.
    """
    def __init__(self, initializer):
        self.initializer = initializer

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, instance, owner):
        from terminedia.image import ShapeView

        if not instance:
            return self
        if isinstance(instance, ShapeView):
            namespace = getattr(instance, "_" + self.name, None)
            if not namespace:
                namespace = self.initializer(instance)
                setattr(instance, "_" + self.name, namespace)
            return namespace
        if not self.name in instance.__dict__:
            instance.__dict__[self.name] = self.initializer(instance)
        return instance.__dict__[self.name]


@lru_cache()
def char_width(char):
    from terminedia.subpixels import BlockChars

    if char in BlockChars.chars:
        return 1
    if len(char) > 1:
        return max(char_width(combining) for combining in char)
    v = unicodedata.east_asian_width(char)
    return 1 if v in ("N", "Na", "A") else 2  # (?) include "A" as single width?


css_colors = {
    "black": (0, 0, 0),
    "silver": (192, 192, 192),
    "gray": (128, 128, 128),
    "white": (255, 255, 255),
    "maroon": (128, 0, 0),
    "red": (255, 0, 0),
    "purple": (128, 0, 128),
    "fuchsia": (255, 0, 255),
    "green": (0, 128, 0),
    "lime": (0, 255, 0),
    "olive": (128, 128, 0),
    "yellow": (255, 255, 0),
    "navy": (0, 0, 128),
    "blue": (0, 0, 255),
    "teal": (0, 128, 128),
    "aqua": (0, 255, 255),
}


_colors_cache = {}


class _ComponentDescriptor:
    def __init__(self, position):
        self.position = position

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, instance, owner):
        if instance is None:
            return self
        instance._components[self.position] = 0

    def __set__(self, instance, value):
        if isinstance(value, float) and 0.0 <= value <= 1.0:
            value = int(value * 255)
        if not 0 <= value <= 255:
            raise f"Color component {self.name} out of range: {value}"
        instance._components[self.position] = value

    def __delete__(self, instance):
        instance._components[self.position] = 0


class Color:
    """One Color class to Rule then all

      Args:
        - value: 3-sequence with floats in 0-1.0 range, or int in 0-255 range, or a string with
                 color in HTML hex notation (3 or 6 digits) or HTML (css) color name

    """

    __slots__ = ("special", "_components", "name")

    red = _ComponentDescriptor(0)
    green = _ComponentDescriptor(1)
    blue = _ComponentDescriptor(2)
    alpha = _ComponentDescriptor(3)

    components = property(lambda s: tuple(s._components[:3]))

    @components.setter
    def components(self, seq):
        for i, value in enumerate(seq):
            self._components[i] = value

    def __init__(self, value=None):
        self._components = bytearray(b"\x00\x00\x00\xff")
        self.special = None
        self.name = ""
        if isinstance(value, Color):
            self.components = value.components
            self.special = value.special

        elif isinstance(value, str):
            if value.startswith("#"):
                self._from_html(value)
            elif value in css_colors:
                self.name = value
                self.components = css_colors[value]
            else:
                raise ValueError(f"Unrecognized color value or name: {value!r}")
        else:
            self.components = self.normalize_color(value)

    def _from_html(self, html):
        html = html.strip("#;")
        if len(html) == 3:
            self.components = tuple(
                (int(html[i], 16) << 4) + int(html[i], 16) for i in (0, 1, 2)
            )
        elif len(html) == 6:
            self.components = tuple(
                int(html[i : i + 2], 16) for i in range(0, 6, 2)
            )
        else:
            raise ValueError(f"Unrecognized color value or name: {value!r}")

    def __len__(self):
        return 3

    def __iter__(self):
        return iter(self.components)

    def __eq__(self, other):
        if not isinstance(other, Color):
            try:
                other = Color(other)
            except (ValueError, TypeError, IndexError):
                return False
        return self.components == other.components

    def __add__(self, other):
        if not isinstance(other, Color):
            other = Color(other)
        return Color(min(255, c1 + c2) for c1, c2 in zip(self, other))

    def __sub__(self, other):
        if not isinstance(other, Color):
            other = Color(other)
        return Color(max(0, c1 - c2) for c1, c2 in zip(self, other))

    def __getitem__(self, index):
        return self._components[index]

    def __setitem__(self, index, value):
        self._components[index] = value

    # red, green, blue = [property(lambda self, i=i: self.components[i]) for i in (0, 1, 2)]
    @classmethod
    def normalize_color(cls, components):
        """Converts RGB colors to use 0-255 integers.

        Args:
          - color: Either a color constant or a 3-sequence,
              with float components on the range 0.0-1.0, or integer components
              in the 0-255 range.

        returns: Color constant, or 3-sequence normalized to 0-255 range.
        """

        components = tuple(components)
        if isinstance(components, tuple) and components in _colors_cache:
            return _colors_cache[components]

        if all(0 <= c <= 1.0 for c in components):
            color = tuple(int(c * 255) for c in components)
        else:
            color = components
        _colors_cache[tuple(components)] = color
        return color

    @property
    def normalized(self):
        return tuple(c/255 for c in self.components)

    @property
    def html(self):
        return "#{:02X}{:02X}{:02X}".format(*(self.components))

    def __repr__(self):
        value = (
            self.special
            if self.special
            else self.name
            if self.name
            else self.components
        )
        return f"<Color {value!r}>"



special_color_names = "DEFAULT_FG DEFAULT_BG CONTEXT_COLORS TRANSPARENT".split()


class SpecialColor(Color):
    """Three to the TTY kings under the sky.

    These are singletons, and some actions on which actual color to
    use will be taken by the code consuming the colors.
    The singleton instances are created in terminedia.values
    """

    __slots__ = ("special", "name", "component_source")

    def __new__(cls, value, component_source=None):
        if value in _colors_cache:
            return _colors_cache[value]
        return super().__new__(cls)

    def __init__(self, value, component_source=None):
        self.special = value
        self.name = value
        self.component_source = component_source
        # no super call.

    def __eq__(self, other):
        return other is self

    @property
    def components(self):
        if not self.component_source:
            return (0, 0, 0)
        if callable(self.component_source):
            return self.component_source(self)
        return self.component_source


class HookList(MutableSequence):
    def __init__(self, initial=None):
        self.data = list()
        if initial is None:
            initial = []
        for item in initial:
            self.append(initial)

    def insert_hook(self, item):
        return item

    def __getitem__(self, index):
        return self.data[index]

    def __setitem__(self, index, item):
        item = self.insert_hook(item)
        self.data[index] = item

    def __delitem__(self, index):
        del self.data[index]

    def __len__(self):
        return len(self.data)

    def insert(self, index, item):
        item = self.insert_hook(item)
        self.data.insert(index, item)

    def __repr__(self):
        return f"{self.__class__.__name__}({self.data!r})"


def get_current_tick():
    """use a coutner global to Screen module, icreased on
    calls to screen.updat()
    """
    from terminedia import context
    return context.ticks if hasattr(context, "ticks") else 0


def tick_forward():
    from terminedia import context
    context.ticks = get_current_tick() + 1


def combine_signatures(func, wrapper=None):
    """Adds keyword-only parameters from wrapper to signature

    Use this in place of `functools.wraps`
    It works by creating a dummy function with the attrs of func, but with
    extra, KEYWORD_ONLY parameters from 'wrapper'.
    To be used in decorators that add new keyword parameters as
    the "__wrapped__"

    Usage:

    def decorator(func):
        @combine_signatures(func)
        def wrapper(*args, new_parameter=None, **kwargs):
            ...
            return func(*args, **kwargs)
    """
    # TODO: move this into 'extradeco' independent package
    from functools import partial, wraps
    from inspect import signature, _empty as insp_empty, _ParameterKind as ParKind
    from itertools import groupby

    if wrapper is None:
        return partial(combine_signatures, func)

    sig_func = signature(func)
    sig_wrapper = signature(wrapper)
    pars_func = {group:list(params)  for group, params in groupby(sig_func.parameters.values(), key=lambda p: p.kind)}
    pars_wrapper = {group:list(params)  for group, params in groupby(sig_wrapper.parameters.values(), key=lambda p: p.kind)}

    def render_annotation(p):
        return f"{':' + (repr(p.annotation) if not isinstance(p.annotation, type) else repr(p.annotation.__name__)) if p.annotation != insp_empty else ''}"

    def render_params(p):
        return f"{'=' + repr(p.default) if p.default != insp_empty else ''}"

    def render_by_kind(groups, key):
        parameters = groups.get(key, [])
        return [f"{p.name}{render_annotation(p)}{render_params(p)}" for p in parameters]

    pos_only = render_by_kind(pars_func, ParKind.POSITIONAL_ONLY)
    pos_or_keyword = render_by_kind(pars_func, ParKind.POSITIONAL_OR_KEYWORD)
    var_positional = [p for p in pars_func.get(ParKind.VAR_POSITIONAL,[])]
    keyword_only = render_by_kind(pars_func, ParKind.KEYWORD_ONLY)
    var_keyword = [p for p in pars_func.get(ParKind.VAR_KEYWORD,[])]

    extra_parameters = render_by_kind(pars_wrapper, ParKind.KEYWORD_ONLY)

    def opt(seq, value=None):
        return ([value] if value else [', '.join(seq)]) if seq else []

    annotations = func.__annotations__.copy()
    for parameter in pars_wrapper.get(ParKind.KEYWORD_ONLY):
        annotations[parameter.name] = parameter.annotation

    param_spec = ', '.join([
        *opt(pos_only),
        *opt(pos_only, '/'),
        *opt(pos_or_keyword),
        *opt(keyword_only or extra_parameters, ('*' if not var_positional else f"*{var_positional[0].name}")),
        *opt(keyword_only),
        *opt(extra_parameters),
        *opt(var_keyword, f"**{var_keyword[0].name}" if var_keyword else "")
    ])
    declaration = f"def {func.__name__}({param_spec}): pass"

    f_globals = func.__globals__
    f_locals = {}

    exec(declaration, f_globals, f_locals)

    result = f_locals[func.__name__]
    result.__qualname__ = func.__qualname__
    result.__doc__ = func.__doc__
    result.__annotations__ = annotations

    return wraps(result)(wrapper)



def contextkwords(func=None, context_path=None):
    if func is None:
        return partial(contextkwords, context_path=context_path)
    sig = inspect.signature(func)
    @combine_signatures(func)
    def wrapper(
        *args,
        char=None,
        color=None,
        foreground=None,
        background=None,
        effects=None,
        # write_transformers=None,
        fill=None,
        context=None,
        **kwargs
    ):
        """
        Decorator to pass decorated function an updated, stacked context
        with all options passed in the call already set.

        If an explicit
        'transformers' if passed will be used to draw the pixels, if it makes sense
        (i.e. the pixels are t    Add a "clear" draw method to empty-up a target.o
        be transformed on write, rather than on reading)

        Existing transformers on the current context will be ignored
        """
        from terminedia import context as root_context
        if not any((char, color, foreground, background, effects, #write_transformers,
                   fill, context)):
            return func(*args, **kwargs)

        self = args[0] if args else None
        if self and not context_path:
            self_context = getattr(self, "context", None)
        else:
            self_context = self
            for comp in context_path.split("."):
                self_context = getattr(self_context, comp)

        color = color or foreground

        parameters = locals().copy()
        context_kw = {attr: parameters[attr] for attr in (
            'char', 'color', 'background', 'effects', #'write_transformers',
            'fill', 'context'
            )
            if parameters[attr]
        }

        work_context = self_context or root_context

        if "context" in sig.parameters:
            kwargs["context"] = work_context

        with work_context(**context_kw):
            return func(*args, **kwargs)
    return wrapper
