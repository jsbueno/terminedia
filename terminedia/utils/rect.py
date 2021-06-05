from .vector import V2


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
        """
        An abstract geometric rectangular area. Mostly used for object sizes.

        It will take any form you get of four numbers representing the 2D coordinates of 2 corners
        of the rectangle to be instantiated - one can pass a 4-number sequence as the first parameter,
        two sequences of 2 pairs as the first 2 parameters, or 4 separate numbers
        representing "x1, y1, x2, y2" as the first 4 parameters. If no coordinate is
        passed at all, a "null rectangle" with coordinates (0, 0, 0, 0) is created;

        If "width_height" as a 2-Sequence or, separately, "witdh" or "height" are passed, these are
        used to compute the second corner of the rectangle.

        If "center" is passed, it is used to translate both corners accordingly.

        This can be used as a parameter almost anywhere a rectangle makes sense in terminedia:
        to define a shape size, to draw an actual rectangle with .draw.rect, as an index
        for a shape, to retrieve a sub-shape. For convenience, those places will also take in
        other Rectangle representing numbers, like a sequence of 4 numbers.

        Rect is a versatile class, with several writable properties that will translate or resize
        the instance as appropriate.
        """
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
        return 2

    def __repr__(self):
        return f"{self.__class__.__name__}({tuple(self.c1)}, {tuple(self.c2)})"
