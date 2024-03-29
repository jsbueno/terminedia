import math
import typing as T
from collections.abc import Sequence, Iterable
from numbers import Real

from colorsys import rgb_to_hsv, hsv_to_rgb

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
                 color in HTML hex notation (3 or 6 digits) or HTML (css) color name, or
                 single number for red component
        - g: single number for green component
        - b: single number for blue component
        - alpha:
        - hsv: 3-sequence with HSV value for color (other components must be left blank)

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


    # temptative typehinting.
    @T.overload
    def __init__(self, value: T.Union[Sequence[Real], Iterable[Real]]): pass
    @T.overload
    def __init__(self, value: Real): pass
    @T.overload
    def __init__(self, red: Real, green: Real, blue: Real, alpha: T.Optional[Real], /): pass
    @T.overload
    def __init__(self, *, hsv: T.Union[Sequence[Real], Iterable[Real]]): pass

    def __init__(self, value=None, g=None, b=None, alpha=None, /, *, hsv=None):
        self._components = bytearray(b"\x00\x00\x00\xff")
        self.special = None
        self.name = ""
        if not hasattr(value, "__len__") and not hasattr(value, "__iter__"):
            if g is not None and b is not None:
                value = (value, g, b, alpha or 0xff)
            elif value is None and hsv is not None:
                self.hsv = hsv
                return
            elif isinstance(value, Real) and g is None and b is None:
                value = (value, value, value)  # use passed value as a gray-level
            else:
                raise ValueError("Pass either 3-components or a sequence of 3/4 components to create a color")

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

        components = tuple(components)
        if isinstance(components, tuple) and components in _colors_cache:
            return _colors_cache[components]

        if all(0 <= c <= 1.0 for c in components[:3]):
            color = tuple(int(c * 255) for c in components[:3])
            if len(components) == 4:
                color += ((components[3] if isinstance(components[3], int) else int(components[3] * 255)) ,)
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

    def isclose(self, other, abs_tol=3) -> bool:
        """Returns True if the other color components are close to this color.

        The RGB components are compared, using the 0-255 number range
        """
        if not isinstance(other, Color):
            other = Color(other)
        return all(math.isclose(c1, c2, rel_tol=0, abs_tol=abs_tol) for c1, c2 in zip(self, other))


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
        _colors_cache[value] = self
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

    # ensure pickle-a-bility:
    def __getstate__(self):
        return None

    def __getnewargs_ex__(self):
        return ((self.name,), {})
