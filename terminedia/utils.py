import unicodedata

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

    def __new__(cls, x=0, y=0):
        """Accepts two coordinates as two parameters for x and y"""
        # Enable working with values defined in Enums
        if hasattr(x, "value"):
            x = x.value
        if hasattr(x, "__len__"):
            x, y = x
        return super().__new__(cls, (x, y))

    def __init__(self, *args, **kw):
        # "Eat" subclass arguments that would
        # otherwise hit tuple.__init__ and
        # cause a fault.
        return
        # If composition of this class ever gets more complex, uncomment the
        # pedantic way to go is:

        #x, y = kw.pop(x, None), kw.pop(y, None)
        #if not x and not y and len(args) >= 2:
            #args = args[2:]
        #super().__init__(*args, **kw)

    x = property(lambda self: self[0])
    y = property(lambda self: self[1])

    def __add__(self, other):
        """Adds both components of a V2 or other 2-sequence"""
        return self.__class__(self[0] + other[0], self[1] + other[1])

    def __sub__(self, other):
        """Subtracts both components of a V2 or other 2-sequence"""
        return self.__class__(self[0] - other[0], self[1] - other[1])

    def __mul__(self, other):
        """multiplies a V2 by an scalar"""
        return self.__class__(self[0] * other, self[1] * other)

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
        locals()[method] = (lambda method: lambda s, *args: getattr(V2, method)(V2(s), *args))(method)

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
        bottom=None, *,
        width_height=None,
        width=None,
        height=None,
        center=None
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

            left = left_or_corner1.start if isinstance(left_or_corner1, slice) else left_or_corner1
            right = left_or_corner1.stop if isinstance(left_or_corner1, slice) else left_or_corner1 + 1
            top = top_or_corner2.start if isinstance(top_or_corner2, slice) else top_or_corner2
            bottom = top_or_corner2.stop if isinstance(top_or_corner2, slice) else top_or_corner2 + 1
        else:
            left = left_or_corner1

        if hasattr(top_or_corner2, "__len__") and len(top_or_corner2) == 2:
            c2 = V2(top_or_corner2)
        elif top is None:
            top = top_or_corner2

        if not width_height and width is not None and height is not None:
            width_height = width, height
        self.c1 = c1 if c1 else (left, top) if left is not None and top is not None else (0, 0)
        self.c2 = c2 if c2 else (right, bottom) if right is not None and bottom is not None else (0, 0)
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
        w2 = w / 2; h2 = h / 2
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

    def __iter__(self):
        yield self.c1
        yield self.c2

    def __len__(self):
        return 4

    def __repr__(self):
        return f"{self.__class__.__name__}({tuple(self.c1)}, {tuple(self.c2)})"


class Color:
    # TODO: a context sensitive color class
    # (to stop yielding constant values to be used as RGB tripplets)
    pass


class LazyBindProperty:
    def __init__(self, initializer):
        self.initializer = initializer

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, instance, owner):
        from terminedia.image import ShapeView
        if not instance:
            return self
        if isinstance(instance, ShapeView):
            namespace = getattr(instance, '_' + self.name, None)
            if not namespace:
                namespace = self.initializer(instance)
                setattr(instance, '_' + self.name, namespace)
            return namespace
        if not self.name in instance.__dict__:
            instance.__dict__[self.name] = self.initializer(instance)
        return instance.__dict__[self.name]


def init_context_for_thread(context, char=None, color=None, background=None, effects=None, direction=None):
    """Create all expected data inside a context in the current thread.

    Multi-threaded apps should call this to update a Screen or Shape instance
    before trying to use that instance in a different thread than its originating one.
    """
    from terminedia.values import DEFAULT_BG, DEFAULT_FG, FULL_BLOCK, Directions, Effects
    context.char = char or FULL_BLOCK
    context.color = color or DEFAULT_FG
    context.background = background or DEFAULT_BG
    context.effects = effects or Effects.none
    context.direction = direction or Directions.RIGHT
    context.transformer = None


def create_transformer(context, slots, clear=False):
    """Attach a specialized callable to a drawing context to transform pixel values during rendering

    Args:
      - context (Drawing context namespace): the context
      - slots (Optional[Union[Constant, Callable[pos, values, context]]]): a sequence of callables that will perform the transform on each channel.
      - clear (bool): if True will replace existing transformers.
                      if False, the new transformation will be appended to the existing transformations in
                      the context.

      The callables passed to "slots" receive the full Pixel values as a sequence
      (for full capability pixels: char, foreground, background, text effects).
      Each callable have to return the final constant that will be applied as
      that component on the drawing target data.

      If one member of "slots" is not callable, it self is used
      as a constant for that channel. The special value `NOP`
      (``terminedia.values.NOP`` means no change to that channel.)

      Slot callables can return the special  `TRANSPARENT` constant to
      indicate the target value at the corresponding plane is preserved.

      Having fewer slots than are planes in the drawing context, means the
      remaining planes are left empty.

      ex. to install a transformer to force all text effects off:
      ```
      from terminedia values import create_transformer, NOP, Effects
      ...
      create_transformer(shape.context, [NOP, NOP, NOP, Effects.none])
      ```

      For a transformer that will force all color rendering
      to be done to the background instead of foreground:
      ```
      create_transformer(shape.context, [NOP, TRANSPARENT, lambda pos, values, context: values[1], NOP])
      ```

      Transfomer to make all printed numbers be printed blinking:

      ```
      create_transformer(shape.context, [NOP, NOP, NOP, lambda pos, values, context: Effects.blink if values[0].isdigit() else TRANSPARENT])
      ```

      To uninstall a transformer, just set it to `None`
      (that is: `shape.context.transformer = None`) or call this with slots=None.

      # TODO -make transformer into a class that allows post-creation introspection and manipulation

    """
    from terminedia.values import NOP

    if not slots:
        context.transformer = None
        return

    previous_transformer = getattr(context, "transformer", None)
    if clear:
        previous_transformer = None

    def transformer(pos, values):
        if previous_transformer:
            values = previous_transformer(pos, values)
        return [
            slot(pos, values, context) if callable(slot) else
            slot if slot is not NOP else
            values[i]
                for i, slot in enumerate(slots)
        ]
    context.transformer = transformer


def char_width(char):
    from terminedia.subpixels import BlockChars
    if char in BlockChars.chars:
        return 1
    if len(char) > 1:
        return max(char_width(combining) for combining in char)
    v = unicodedata.east_asian_width(char)
    return 1 if v in ("N", "Na") else 2   # (?) include "A" as single width?
