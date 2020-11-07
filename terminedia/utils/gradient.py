from __future__ import annotations

import typing as T

from .colors import Color


# NB. at this point, annotations are not made in a strict way to pass mypy or other
# tooling checking, and are intended as documntation hints only


#: Add or subtract this value when inserting a new gradient stop to change the
#: color immediatelly after or immediatelly before an existing stop:
EPSILON = .0000001


class Gradient:
    def __init__(self, stops: T.Sequence[T.Tuple[float, Color]]):
        """Define a gradient.
        Args:
           stops: list where each component is a 2-tuple - the first item
           is a 0<= numbr <= 1, the second is a color.

        use __getitem__ (gradient[0.3]) to get the color value at that point.
        """
        # Promote stops[1] to proper colors:
        self.parent = None
        stops = [(stop[0], Color(stop[1]), *stop[2:]) for stop in stops]
        self.stops = sorted(stops, key=lambda stop: (stop[0], stops.index(stop)))
        # "root" gradients are always 0-1 range. Use the .scale method to get
        # a child gradient that stretches from 0 to the scale factor.
        self.scale_factor = 1

    def __getitem__(self, position):
        position /= self.scale_factor
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

        # Linear color segments - in the future we can use a curve function;
        scale = 1 / (p_start - p_previous)
        weight_from_previous = 1 - ((position - p_previous) * scale)
        weight_from_next = 1 - ((p_start - position) * scale)

        c_previous = c_previous.normalized
        color = color.normalized
        return Color(
            (
                min(
                    1.0,
                    c_previous[i] * weight_from_previous + color[i] * weight_from_next,
                )
                for i in (0, 1, 2)
            )
        )


    def __setitem__(self, position, color, *args):

        color = Color(color)
        position /= self.scale_factor

        for i, (p_start, *_) in enumerate(self.stops):
            if p_start == position:
                self.stops[i] = (position, color, *args)
            if p_start > position:
                # new stop:
                self.stops.insert(i, (position, color, *args))
                break
        else:
            self.stops.append((position, color, *args))

    @property
    def root(self):
        root = self
        while root.parent:
            root = root.parent
        return root

    def scale(self, scale_factor) -> Gradient:
        new_gr = Gradient.__new__(self.__class__)
        new_gr.stops = self.stops
        new_gr.scale_factor = self.scale_factor * scale_factor
        new_gr.parent = self
        return new_gr

    def __repr__(self):
        return f"Gradient({self.stops})"
