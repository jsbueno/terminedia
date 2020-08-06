from .vector import V2
from numbers import Number

class Rect:
    __slots__ = ("_c1", "_c2")
    __match_args__ = ("c1", "c2")

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

        kw = {"c1": left_or_corner1, "c2": top_or_corner2, "right": right, "bottom": bottom,
              "width_height": width_height, "width": width, "height": height, "center": center}

        match kw:
            case {"c1": (c1:=(_, _)), "c2": (c2:=(_, _))}: pass
            case {"c1": Rect(c1, c2)}: pass
            case {"c1": Number(), "c2": Number(), "right": Number(), "bottom": Number()}:
                c1, c2 = (kw["c1"], kw["c2"]), (right, bottom)
            case {"c1": (_, _, _, _)}:
                c1, c2 = kw["c1"][:2], kw["c1"][2:]
            case {"c1": (c1:=(_, _)), "width_height": (_, _)}:
                c2 = c1 + V2(width_height)
            case {"c1": (c1:=(_, _)), "width": Number(), "height": Number()}:
                c2 = c1 + V2(width, height)
            case {"c1": (c1:=(_, _)), "c2": None, "right": Number(), "bottom": Number()}:
                c2 = bottom, right
            case {"c1": None, "right": Number(), "bottom": Number(), "center": (_, _)}:
                c1 = 0, 0
                c2 = bottom, right
            case {"c1": (c2:=(_, _)), "c2": None}:
                c1 = 0, 0
            case _:
                c1, c2 = (0, 0)

        self.c1 = V2(c1)
        self.c2 = V2(c2)
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
            (other.top <= self.top <= other.bottom or
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
                yield V2(x, y)

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
