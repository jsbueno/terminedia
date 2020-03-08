import inspect
import operator
import unicodedata
from collections.abc import MutableSequence, MutableMapping, Iterable, Mapping
from colorsys import rgb_to_hsv, hsv_to_rgb
from functools import lru_cache, wraps, partial


root_context = None


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

    __rmul__ = __mul__

    def __truediv__(self, other):
        try:
            other = 1 / other
        except (ValueError, TypeError):
            return NotImplemented
        return self * other

    def __floordiv__(self, other):
        return self.__class__(self[0] // other, self[1] // other)

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
            else c1 + width_height if width_height
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

    @property
    def as_tuple(self):
        return tuple((*self.c1, *self.c2))

    def intersection(self, other):
        cls = self.__class__
        if not isinstance(other, Rect):
            other = cls(other)
        if not self.collide(other):
            return None
        result = cls((
            max(self.left, other.left), max(self.top, other.top),
            min(self.right, other.right), min(self.bottom, other.bottom)
        ))
        return result

    def __iter__(self):
        yield self.c1
        yield self.c2

    def iter_cells(self):
        for y in range(self.top, self.bottom):
            for x in range(self.left, self.right):
                yield V2(x,y)

    def __add__(self, other):
        if isinstance(other, V2) or len(other) == 2:
            return self.__class__(self.c1 + other, self.c2 + other)
        raise NotImplementedError()

    def __sub__(self, other):
        if isinstance(other, V2) or len(other) == 2:
            return self.__class__(self.c1 - other, self.c2 - other)
        raise NotImplementedError()

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
    def __init__(self, initializer=None, type=None):
        self.type = type
        if not initializer:
            return
        self.initializer = initializer

    def __call__(self, initializer):
        self.initializer = initializer
        return self

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

    def __set__(self, instance, value):
        if self.type and not isinstance(value, self.type):
            raise AttributeError(f"{self.name!r} must be set to {self.type} instances on {instance.__class__.__name__} objects.")
        instance.__dict__[self.name] = value

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
        return instance._components[self.position]

    def __set__(self, instance, value):
        if isinstance(value, float) and 0.0 <= value <= 1.0:
            value = int(value * 255)
        instance._components[self.position] = value
        instance.name = ""

    def __delete__(self, instance):
        self.__set__(instance, 0)


class _ComponentHSVDescriptor(_ComponentDescriptor):

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return instance.hsv[self.position]

    def __set__(self, instance, value):
        hsv = list(instance.hsv)
        hsv[self.position] = value
        instance.hsv = hsv

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

    hue = _ComponentHSVDescriptor(0)
    saturation = _ComponentHSVDescriptor(1)
    value = _ComponentHSVDescriptor(2)

    components = property(lambda s: tuple(s._components[:3]))

    @components.setter
    def components(self, seq):
        for i, value in enumerate(seq):
            self._components[i] = value
        self.name = ""

    def __init__(self, value=None, hsv=None):
        self._components = bytearray(b"\x00\x00\x00\xff")
        self.special = None
        self.name = ""
        if value is None and hsv is not None:
            self.hsv = hsv
            return
        if isinstance(value, Color):
            self.components = value.components
            self.special = value.special

        elif isinstance(value, str):
            if value.startswith("#"):
                self._from_html(value)
            elif value in css_colors:
                self.components = css_colors[value]
                self.name = value
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
        if 0.0 <= value <= 1.0 and not (isinstance(value, int) and value == 1):
            value = int(value * 255)
        self._components[index] = value
        self.name = ""

    @classmethod
    def normalize_color(cls, components):
        """Converts RGB colors to use 0-255 integers.

        Args:
          - color: Either a color constant or a 3-sequence,
              with float components on the range 0.0-1.0, or integer components
              in the 0-255 range.

        returns: Color constant, or 3-sequence normalized to 0-255 range.
        """

        if isinstance(components, (int, float)):
            components = (components, components, components)
        else:
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

    @property
    def hsv(self):
        return rgb_to_hsv(*self.normalized)

    @hsv.setter
    def hsv(self, values):
        self.components = self.normalize_color(hsv_to_rgb(*values))


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


class Gradient:
    def __init__(self, stops):
        """Define a gradient.
        Args:
           stops: list where each component is a 2-tuple - the first item
           is a 0<= numbr <= 1, the second is a color.

        use __getitem__ (grdient[0.3]) to get the color value at that point.
        """
        # Promote stops[1] to proper colors:
        stops = [(stop[0], Color(stop[1]), *stop[2:]) for stop in stops]
        self.stops = sorted(stops, key=lambda stop: (stop[0], stops.index(stop)))

    def __getitem__(self, position):
        p_previous = -1
        c_previous = self.stops[0][1]
        for p_start, color, *_ in self.stops:
            if p_previous < position <= p_start:
                break
            p_previous = p_start
            c_previous = color
        else:
            return color
        if p_previous == -1 or p_start == p_previous:
            return color
        scale = 1 / (p_start - p_previous)
        weight_from_previous = 1 - ((position - p_previous) * scale)
        weight_from_next = 1 - ((p_start - position) * scale)

        c_previous = c_previous.normalized
        color = color.normalized
        return Color((
            min(1.0, c_previous[i] * weight_from_previous + color[i] * weight_from_next) for i in (0,1,2)
        ))

    def __repr__(self):
        return f"Gradient({self.stops})"



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
    """use a counter global to Screen module, increased on
    calls to screen.update()
    """
    global root_context
    if not root_context:
        from terminedia import context as root_context
    return root_context.ticks if hasattr(root_context, "ticks") else 0


def tick_forward():
    global root_context
    if not root_context:
        from terminedia import context as root_context
    root_context.ticks = get_current_tick() + 1


def combine_signatures(func, wrapper=None, include=None):
    """Adds keyword-only parameters from wrapper to signature

    Args:
      - func: The 'user' func that is being decorated and replaced by 'wrapper'
      - wrapper: The 'traditional' decorator which keyword-only parametrs should be added to the
            wrapped-function ('func')'s signature
      - include: optional list of keyword parameters that even not being present
            on the wrappers signature, will be included on the final signature.
            (if passed, these named arguments will be part of the kwargs)

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
        return partial(combine_signatures, func, include=include)

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
    if include:
        if isinstance(include[0], Mapping):
            include = [f"{param['name']}{':' + param['annotation'] if 'annotation' in param else ''}{'=' + param['default'] if 'default' in param else ''}" for param in include]
        else:
            include = [f"{name}=None" for name in include]

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
        *opt(include),
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



def contextkwords(func=None, context_path=None, text_attrs=False):
    if func is None:
        return partial(contextkwords, context_path=context_path, text_attrs=text_attrs)
    sig = inspect.signature(func)
    @combine_signatures(func, include=["font", "direction"] if text_attrs else None)
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
        global root_context
        if not root_context:
            from terminedia import context as root_context
        if text_attrs:
            font = kwargs.pop("font", None)
            direction = kwargs.pop("direction", None)
        else:
            font = direction = None
        if all(attr is not None for attr in(char, color, foreground, background, effects, #write_transformers,
                   fill, *([font, direction] if text_attrs else []), context)):
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
            'fill', 'font', 'direction', 'context'
            )
            if parameters[attr] is not None
        }

        work_context = self_context or root_context

        if "context" in sig.parameters:
            kwargs["context"] = work_context

        with work_context(**context_kw):
            return func(*args, **kwargs)
    return wrapper


import threading

class TaggedDictionary(MutableMapping):
    """Mapping that allows key/value pairs to have attached tags

    when using the tags in browsing (values, keys), a tag may be specifed
    to filter out any pairs that do not have the same tag.

    How it works: When creating an item, if the key is a tuple,
    all components are considered "tags" - on retrieving an item,
    any tag will retrieve a collection of all itens with that tag.

    Special set funcionality applies to allow retrieving by more than
    one tag as an "and" operation.

    Also, for temporary working of a subset of the contents, say,
    all items that have the "animal" tag, one can call the ".view" with
    the desired tags - the view will point to the original data,
    but only make visible the itens with the requested tags.
    Items added to the view will have the view tags applied. Items
    added with the ".add" method instead of the `x[y] = z` mapping
    syntax will be added to a unique handle id, and associated
    with the current view tags. (the unique id is unique within
    the parent mapping)

    """
    # TODO: move this to "extradict" package and make a new release

    def __init__(self, initial_contents: Mapping = None):
        self.data = {}
        self._keys = {}
        self._filtering_keys = set()
        self._lock = threading.Lock()
        self._counter = [0]
        if initial_contents:
            self.update(initial_contents)

    def view(self, keys):
        cls = self.__class__
        new = cls.__new__(cls)
        new.data = self.data
        new._lock = self._lock
        new._keys = self._keys
        new._filtering_keys = self._get_local_keys(keys)
        new._counter = self._counter
        return new

    def _get_local_keys(self, keys):
        if not isinstance(keys, Iterable) or isinstance(keys, str):
            keys = {keys,}
        return frozenset((*self._filtering_keys, *keys))

    def __setitem__(self, keys, value):
        keys = self._get_local_keys(keys)
        with self._lock:
            self.data[keys] = value
            for key in keys:
                self._keys.setdefault(key, set()).add(keys)
            self._counter[0] += 1

    def _get_resolved_keys(self, keys):
        keys = self._get_local_keys(keys)
        if keys:

            keysets = [self._keys[key] for key in keys if key in self._keys]
            if len(keysets) < len(keys):
                unknown = set()
                for key in keys:
                    if key not in self._keys and key not in self._filtering_keys:
                        unknown.add(key)
                if unknown:
                    raise KeyError(repr(unknown))

            keysets = iter(keysets)
            resolved_keys = next(keysets, set())
            for keyset in keysets:
                resolved_keys = resolved_keys.intersection(keyset)
        else:
            resolved_keys = set(self.data.keys())
        return resolved_keys

    def __getitem__(self, keys):
        result = [self.data[keys] for keys in self._get_resolved_keys(keys)]
        if not result:
            raise KeyError(repr(keys))
        return result

    def __delitem__(self, keys):
        keys = self._get_local_keys(keys)
        resolved_keys = self._get_resolved_keys(keys)
        with self._lock:
            for outter_key in keys:
                to_remove = set()
                for inner_key in self._keys[outter_key]:
                    if outter_key in inner_key:
                        to_remove.add(inner_key)
                self._keys[outter_key] -= to_remove
                if not self._keys[outter_key]:
                    del self._keys[outter_key]
            for key in self._get_resolved_keys(()):
                del self.data[key]

    def add(self, value):
        """Creates a unique tag for an item and add it in the current view

        Allows items to be added under selected tags under a view,
        without having to worry about unique identifiers within those tags

        Returns the unique key attributed to the item.
        """
        key = f"_id_{self._counter[0]}"
        self[key] = value
        return key

    def remove(self, value):
        key = sentinel = object()
        for key, other_value in self.items():
            if other_value == value:
                break
        else:
            if key is not sentinel:
                del self[key]
                return
        raise ValueError("Value not in TaggedDictionary")

    def __iter__(self):
        return iter(self._get_resolved_keys(()))

    def __len__(self):
        return len(self._get_resolved_keys(()))

    def values(self):
        return [item[0] for item in super().values()]

    def __repr__(self):
        keys = self._get_resolved_keys(())
        repr_keys = {(keys - self._filtering_keys) for keys in keys}
        result = "TaggedDictionary({{{}}})".format(", ".join(f"{tuple(key)}:{value!r}" for key, value in self.items()))
        if self._filtering_keys:
            result += "view({})".format(", ".join(repr(key) for key in self._filtering_keys))
        return result


