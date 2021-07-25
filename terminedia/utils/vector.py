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
        if isinstance(x, str) and x.upper() in {"RIGHT", "LEFT", "UP", "DOWN"}:
            from terminedia import Directions
            return getattr(Directions, x.upper())
        if hasattr(x, "value"):
            x = x.value
        if hasattr(x, "__len__") or hasattr(x, "__iter__"):
            x, y = x
        elif x is None:
            x = y = 0
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
        """multiplies a V2 by an scalar or by another Seq[2] (item by item)"""
        if hasattr(other, "__len__") and len(other) == 2:
            return self.__class__(self[0] * other[0], self[1] * other[1])
        return self.__class__(self[0] * other, self[1] * other)

    __rmul__ = __mul__

    def __truediv__(self, other):
        try:
            other = 1 / other
        except (ValueError, TypeError):
            if len(other) == 2:
                return self.__class__((self[0] / other[0], self[1] / other[1]))
            else:
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

    @property
    def area(self):
        return self.x * self.y


class NamedV2(V2):
    """Vector meant to be used as constant, with a string-repr name"""

    name = None

    def __init__(self, *args, name=None, **kw):
        """Optional name - if used as a descriptor, name is auto-set"""

        # this method is called more than once when
        # recreating a direction from a string-name
        if not self.name:
            self.name = name
        super().__init__(*args, **kw)

    def __set_name__(self, owner, name):
        if not self.name:
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
    for method in "__add__ __sub__ __mul__ __abs__ __truediv__ __floordiv__ as_int".split():
        locals()[method] = (
            lambda method: lambda s, *args: getattr(V2, method)(V2(s), *args)
        )(method)

    @property
    def value(self):
        """Returns self, keeping compatibility with Python Enums if used as a descriptor"""
        return self
