import typing as T

from .colors import Color


# NB. at this point, annotations are not made in a strict way to pass mypy or other
# tooling checking, and are intended as documntation hints only


#: Add or subtract this value when inserting a new gradient stop to change the
#: color immediatelly after or immediatelly before an existing stop:
EPSILON = .0000001


class Gradient:

    BASE_TYPE = float

    def __init__(self, stops: T.Sequence[T.Tuple[float, T.Any]]):
        """Define a gradient.
        Args:
           stops: list where each component is a 2-tuple - the first item
           is a 0<= numbr <= 1, the second is a value of the type to be interpolated.
           The base Gradient class works with float numbers. Subclasses like
           ColorGradient interpolate other kind of values.

        use __getitem__ (i.e. gradient[0.3]) to get the value at that point.
        """
        # Promote stops[1] to proper colors:
        self.parent = None
        stops = [(stop[0], self.BASE_TYPE(stop[1]), *stop[2:]) for stop in stops]
        self.stops = sorted(stops, key=lambda stop: (stop[0], stops.index(stop)))
        # "root" gradients are always 0-1 range. Use the .scale method to get
        # a child gradient that stretches from 0 to the scale factor.
        self.scale_factor = 1

    def __getitem__(self, position):
        position /= self.scale_factor
        p_previous = -1
        c_previous = self.stops[0][1]
        for p_start, c_next, *_ in self.stops:
            if p_previous < position <= p_start:
                break
            p_previous = p_start
            c_previous = c_next
        else:
            return c_next
        if p_previous == -1 or p_start == p_previous:
            return c_next

        # Linear color segments - in the future we can use a curve function;
        scale = 1 / (p_start - p_previous)
        weight_from_previous = 1 - ((position - p_previous) * scale)
        weight_from_next = 1 - ((p_start - position) * scale)

        return self.interpolate(c_previous, c_next, weight_from_previous, weight_from_next)

    def interpolate(self, previous, next_, weight_from_previous, weight_from_next):
        """Interpolation that works for linear numeric values"""
        return previous * weight_from_previous + next_ * weight_from_next


    def __setitem__(self, position, value, *args):

        if not isinstance(value, self.BASE_TYPE):
            value = self.BASE_TYPE(value)

        position /= self.scale_factor

        for i, (p_start, *_) in enumerate(self.stops):
            if p_start == position:
                self.stops[i] = (position, value, *args)
            if p_start > position:
                # new stop:
                self.stops.insert(i, (position, value, *args))
                break
        else:
            self.stops.append((position, value, *args))

    @property
    def root(self):
        root = self
        while root.parent:
            root = root.parent
        return root

    def scale(self, scale_factor) -> "Gradient":
        new_gr = self.__class__.__new__(self.__class__)
        new_gr.stops = self.stops
        new_gr.scale_factor = self.scale_factor * scale_factor
        new_gr.parent = self
        return new_gr

    def __repr__(self):
        return f"{self.__class__.__name__}({self.stops})"


class ColorGradient(Gradient):
    BASE_TYPE = Color

    def interpolate(slf, c_previous, c_next, weight_from_previous, weight_from_next):

        c_previous = c_previous.normalized
        c_next = c_next.normalized
        return Color((min(1.0,
                 c_previous[i] * weight_from_previous + c_next[i] * weight_from_next,
            ) for i in (0, 1, 2)
        ))


class RangeMap:
    """Helper class -

    given a number on getitem, define the imediate lower number
    set in "stops".
    """
    def __init__(self, stops: T.List[int]):
        self.stops = stops

    def __getitem__(self, item):
        prev_s = self.stops[0]
        for s in self.stops:
            if item < s:
                return prev_s, s
            prev_s = s
        return prev_s, s

    def __repr__(self):
        return f"{self.__class__.__name__}({self.stops})"
