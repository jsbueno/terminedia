from .colors import Color


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
        return Color(
            (
                min(
                    1.0,
                    c_previous[i] * weight_from_previous + color[i] * weight_from_next,
                )
                for i in (0, 1, 2)
            )
        )

    def __repr__(self):
        return f"Gradient({self.stops})"
