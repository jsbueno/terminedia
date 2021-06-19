import inspect
from collections.abc import Sequence

from terminedia.image import RasterUndo
from terminedia.subpixels import BlockChars, HalfChars
from terminedia.values import CONTEXT_COLORS, EMPTY, TRANSPARENT, DEFAULT_BG, DEFAULT_FG, Directions
from terminedia.utils import V2, Rect, contextkwords


class Drawing:
    """Drawing and rendering API

    An instance of this class is attached to :any:`Screen` and :any:`Shape`
    instances as the :any:`draw` attribute, and as the `.high.draw` and `.braile.draw`
    attributed for drawing with 1/4 and 1/8 block characters.
    All context-related information is kept on the associated screen instance,
    the public methods here issue pixel setting and resetting at the owner -
    using that owners's context colors and other attributes.

    That is - the typical usage for methods here will be ``screen.draw.line((0,0)-(50,20))``
    """

    def __init__(self, set_fn, reset_fn, get_fn, size_fn, context):
        """Not intented to be instanced directly -

        Args:
          - set_fn (callable): function to set a pixel
          - reset_fn (callable): function to reset a pixel
          - size_fn (callable): function to retrieve the width and height of the output
          - context : namespace where screen attributes are set

        This takes note of the callback functions for
        owner-size, pixels set and reset and the drawing context.
        This call is made automatically on Screen instantiation, or
        lazily when the `.draw` attribute is requested on a shape.
        The first parameter to both reset_fn and set_fn is a 2D position
        where it should render a pixel according to the current context.
        If the callable for `set_fn` accepts 2 parameters, the second
        one should optionally accept a terminedia.images.Pixel object,
        and decide how to render it.
        """
        self.set = set_fn
        self.get = get_fn
        self.reset = reset_fn
        self._size = size_fn
        self.context = context

    @property
    def size(self):
        return self._size()

    @contextkwords
    @RasterUndo.undoable
    def line(self, pos1, pos2, erase=False):
        """Draws a straight line connecting both coordinates.

        Args:
          - pos1 (2-tuple): starting coordinates
          - pos2 (2-tuple): ending coordinates
          - erase (bool): Whether to draw (set) or erase (reset) pixels.

        Public call to draw an arbitrary line using character blocks
        on the terminal.
        The color line is defined in the passed parameter or from the context.
        """

        op = self.reset if erase else self.set
        pos1 = V2(pos1)
        pos2 = V2(pos2)

        op(pos1)

        max_manh = max(abs(pos2.x - pos1.x), abs(pos2.y - pos1.y))
        if max_manh == 0:
            return
        step_x = (pos2.x - pos1.x) / max_manh
        step_y = (pos2.y - pos1.y) / max_manh
        total_manh = 0
        while total_manh < max_manh:
            pos1 += (step_x, step_y)
            total_manh += max(abs(step_x), abs(step_y))
            op(pos1.as_int)

    @contextkwords
    @RasterUndo.undoable
    def rect(self, pos1, pos2=(), *, rel=(), erase=False):
        """Draws a rectangle

        Args:
          - pos1 (Union[Rectangle, 2-tuple]): top-left coordinates
          - pos2 (Optional[2-tuple]): bottom-right limit coordinates. If not given, pass "rel" instead
          - rel (Optional[2-tuple]): (width, height) of rectangle. Ignored if "pos2" is given
          - fill (bool): Whether fill-in the rectangle, or only draw the outline. Defaults to False.
          - erase (bool): Whether to draw (set) or erase (reset) pixels.

        Public call to draw a rectangle using character blocks
        on the terminal.
        The color line is defined in the owner's context.color
        attribute. In the case of high-resolution drawing, the background color
        is also taken from the context.
        """
        pos1, pos2 = Rect(pos1, pos2, width_height=rel)
        # Ending interval is open, just as Python works with intervals.
        pos2 -= (1, 1)

        fill = self.context.fill

        x1, y1 = pos1
        x2, y2 = pos2
        self.line(pos1, (x2, y1), erase=erase)
        self.line((x1, y2), pos2, erase=erase)
        if (fill or erase) and y2 != y1:
            direction = int((y2 - y1) / abs(y2 - y1))
            for y in range(y1 + 1, y2, direction):
                self.line((x1, y), (x2, y), erase=erase)
        else:
            self.line(pos1, (x1, y2))
            self.line((x2, y1), pos2)

    @contextkwords
    def fill(self):
        """Fills the associated target with current context values
        Args:

        The context attributes are used to fill the target area.
        """
        self.rect((0, 0), self.size, fill=True)

    @contextkwords
    @RasterUndo.undoable
    def floodfill(self, pos, threshold=None):
        """Fills the associated target with context values, starting at seed "pos".

        Any different parameters for target pixels are considered boundaries
        "threshold" may be passed a guard callable which will take each target
        pixel, and should return "False" if it should be painted and "True"
        if it is a boundary.
        Args:
            - pos (V2|Sequence[2]): initial position
            - threshold (Optional[Callable[Pixel, Pixel, Pos]): callable - takes initial value at origin, and target pixel value.
                    Should return 'True' for boundary pixels, False if pixel is to be painted.
        The context attributes are used to fill the target area.
        """
        seed = self.get(pos)
        if threshold is None:
            threshold = lambda seed, target, pos: seed != target

        rect = Rect(self.size)

        fillable = set()
        visited = set()

        to_check = {pos,}

        while to_check:
            pos = to_check.pop()
            if pos in visited:
                continue
            visited.add(pos)
            if threshold(seed, self.get(pos), pos):
                continue
            fillable.add(pos)
            for direction in Directions:
                target = pos + direction
                if target in rect:
                    to_check.add(target)
        for pos in fillable:
            self.set(pos)


    def _link_prev(self, pos, i, limits, mask):
        if i < limits[0] - 1:
            for j in range(i, limits[0]):
                self.set((pos[0] + j, pos[1]))
                mask[j] = True
        elif i + 1 > limits[1]:
            for j in range(limits[1], i):
                self.set((pos[0] + j, pos[1]))
                mask[j] = True

    @contextkwords
    @RasterUndo.undoable
    def ellipse(self, pos1, pos2=(), *, rel=()):
        """Draws an ellipse

        Args:
          - pos1 (Union[Rectangle, 2-tuple]): top-left coordinates
          - pos2 (Optional[2-tuple]): bottom-right limit coordinates. If not given, pass "rel" instead
          - rel (Optional[2-tuple]): (width, height) of rectangle. Ignored if "pos2" is given

        Public call to draw an ellipse using character blocks
        on the terminal.
        The color line is defined in the owner's context.color
        attribute. In the case of high-resolution drawing, the background color
        is also taken from the context.
        """
        pos1, pos2 = Rect(pos1, pos2, width_height=rel)

        pos2 -= (1, 1)

        return (
            self._empty_ellipse(pos1, pos2)
            if not self.context.fill
            else self._filled_ellipse(pos1, pos2)
        )

    def _filled_ellipse(self, pos1, pos2):
        from math import cos, asin

        x1, y1 = pos1
        x2, y2 = pos2

        x1, x2 = (x1, x2) if x1 <= x2 else (x2, x1)
        y1, y2 = (y1, y2) if y1 <= y2 else (y2, y1)

        cx, cy = x1 + (x2 - x1) / 2, y1 + (y2 - y1) / 2
        r1, r2 = x2 - cx, y2 - cy

        for y in range(y1, y2 + 1):
            sin_y = abs(y - cy) / r2
            az = asin(sin_y)
            r_y = abs(V2(r2 * sin_y, r1 * cos(az)))
            for i, x in enumerate(range(x1, x2 + 1)):
                d = abs(V2(x - cx, y - cy))

                if d <= r_y:
                    self.set((x, y))

    def _empty_ellipse(self, pos1, pos2):
        from math import sin, cos, pi

        x1, y1 = pos1
        x2, y2 = pos2

        cx, cy = x1 + (x2 - x1) / 2, y1 + (y2 - y1) / 2

        rx = abs(pos1[0] - cx)
        ry = abs(pos1[1] - cy)
        factor = 0.25

        t = 0
        step = pi / (2 * max(rx, ry))

        ox = round(rx + cx)
        oy = round(cy)
        self.set((ox, oy))

        while t < 2 * pi:
            t += step
            x = round(rx * cos(t) + cx)
            y = round(ry * sin(t) + cy)
            if abs(x - ox) > 1 or abs(y - oy) > 1:
                t -= step
                step *= 1 - factor
                factor *= 0.8
            elif x == ox and y == oy:
                t -= step
                step *= 1 + factor
                factor *= 0.8
            else:
                factor = 0.25

            self.set((x, y))
            ox, oy = x, y

    @contextkwords
    @RasterUndo.undoable
    def bezier(self, pos1, pos2, pos3, pos4, *extra):
        """Draws a bezier curve given the control points

        Args:
            pos1 (2-sequence): Fist control point
            pos2 (2-sequence): Second control point
            pos3 (2-sequence): Third control point
            pos4 (2-sequence): Fourth control point
            extra Tuple[2-sequence]: n-sets of 3 more control points to keep drawing.
        """
        pos1 = V2(pos1)
        pos2 = V2(pos2)
        pos3 = V2(pos3)
        pos4 = V2(pos4)
        x, y = pos1

        t = 0
        step = 1 / (abs(pos4 - pos3) + abs(pos3 - pos2) + abs(pos2 - pos1))
        self.set((x, y))
        while t <= 1.0:

            x, y = (
                pos1 * (1 - t) ** 3
                + pos2 * 3 * (1 - t) ** 2 * t
                + pos3 * 3 * (1 - t) * t ** 2
                + pos4 * t ** 3
            )

            self.set((round(x), round(y)))
            t += step
        if len(extra) >= 3:
            self.bezier(pos4, extra[0], extra[1], extra[2], *extra[3:])


    @RasterUndo.undoable
    def blit(self, pos, data, *, roi=None, color_map=None, erase=False):
        """Blits a blocky image in the associated screen at POS

        Args:
          - pos (Union[2-sequence, Rectangle]): top-left corner of where to blit, or a rectangle with extents to be blitted.
          - shape (Shape/string/list): Shape object or multi-line string or list of strings with shape to be drawn
          - roi (Optional[Rect]): (Region of interest) delimiting rectangle in source image(data) to be blitted.
                                 Defaults to whole image.
          - color_map (Optional mapping): palette mapping chracters in shape to a color
          - erase (bool): if True white-spaces are erased, instead of being ignored. Default is False. FIXME: under the Pixel model, erase is always True.

        Shapes return specialized Pixel classes when iterated upon -
        what is set on the screen depends on the Pixel returned.
        As of version 0.3dev, Shape class returns a pixel
        that has a True or False value and a foreground color (or no color) -
        support for other Pixel capabilities is not yet implemented.

        """
        from terminedia.image import Shape, PalettedShape, SKIP_LINE

        if not hasattr(self.context, "color_stack"):
            self.context.color_stack = []
        if not hasattr(self.context, "background_stack"):
            self.context.background_stack = []

        self.context.color_stack.append(self.context.color)
        self.context.background_stack.append(self.context.background)

        if isinstance(data, (str, list)):
            shape = PalettedShape(data, color_map)
        elif isinstance(data, Shape):
            shape = data
        else:
            raise TypeError(
                f"Unknown data argument passed to blit: {type(data)} instance"
            )

        if isinstance(pos, Rect):
            extent = pos.width_height
            pos = pos.c1
        else:
            extent = None

        if roi is not None:
            roi = Rect(roi)
            shape = shape[roi]

        direct_pix = len(inspect.signature(self.set).parameters) >= 2

        ishape = iter(shape)
        while True:
            pixel_pos, pixel = next(ishape, (None, None))
            if pixel_pos is None:
                break
            target_pos = pos + pixel_pos
            if extent and (target_pos.x >= extent.x or target_pos.y >= extent.y):
                ishape.send(SKIP_LINE)
                continue
            should_set = (
                pixel.capabilities.value_type == str
                and (
                    pixel.value != EMPTY
                    or pixel.value == "."
                    and pixel.capabilities.translate_dots
                )
                or pixel.capabilities.value_type == bool
                and pixel.value
            )
            if not should_set and not erase:
                continue
            if direct_pix:
                if (
                    pixel.capabilities.has_foreground and pixel.foreground == CONTEXT_COLORS or
                    pixel.capabilities.has_background and pixel.background == CONTEXT_COLORS
                ):
                    _cls = pixel.__class__
                    values = [pixel.value]
                    if pixel.capabilities.has_foreground:
                        values.append(
                        pixel.foreground if pixel.foreground != CONTEXT_COLORS else self.context.color_stack[-1]
                    )
                    if pixel.capabilities.has_background:
                        values.append(
                        pixel.background if pixel.foreground != CONTEXT_COLORS else self.context.background_stack[-1]
                    )
                    if pixel.capabilities.has_effects:
                        values.append(pixel.effects)

                    pixel = _cls(*values)
                self.set(target_pos, pixel)
            else:
                if pixel.capabilities.has_foreground:
                    if pixel.foreground == CONTEXT_COLORS:
                        self.context.color = self.context.color_stack[-1]
                    else:
                        self.context.color = pixel.foreground
                if pixel.capabilities.has_background:
                    if pixel.background == CONTEXT_COLORS:
                        self.context.background = self.context.background_stack[-1]
                    else:
                        self.context.background = pixel.background

                if should_set:
                    self.set(target_pos)
                else:
                    self.reset(target_pos)

        self.context.color = self.context.color_stack.pop()
        self.context.background = self.context.background_stack.pop()


class HighResBase:
    """ Provides a seamless mechanism to draw using unicode special characters as pixels.

    This is used as a base to have the method used for drawing using 1/4 block characters,
    Braile characters, vintage "sextant" 1/6 blocks and possibly others to come.

    Keep in mind that while it is possible to emulate the higher resolution
    pixels, screen colors are limited to character positions, so color
    on these pixels will "leak" to their block. (Users familiar
    with the vintage 8 bit ZX-Spectrum should feel at home)

    This class should not be instanced or used directly - instead, call the `Drawing` methods
    in the associated `draw` class as in `screen.high.draw.blit(position, image)`

    """

    def __init__(self, parent, block_class=BlockChars, block_width=2, block_height=2):
        """Sets instance attributes"""
        self.block_class = block_class
        self.block_width = block_width
        self.block_height = block_height

        self.parent = parent
        self.draw = Drawing(
            self.set_at, self.reset_at, self.get_at, self.get_size, self.parent.context
        )
        self.context = parent.context

    def get_size(self):
        """Returns the width and height available at high-resolution based on parent's Screen size"""
        w, h = self.parent.get_size()
        return V2(w * self.block_width, h * self.block_height)

    size = property(get_size)
    width = property(lambda s: s.get_size()[0])
    height = property(lambda s: s.get_size()[1])

    def operate(self, pos, operation):
        """Internal -

        Common code to calculate the coordinates and get/reset/query a pixel at the correct sub-block resolution.
        Call  :any:`HighRes.set_at`, :any:`HighRes.reset_at` or :any:`HighRes.get_at` instead.
        """
        from terminedia.image import Pixel

        p_x = pos[0] // self.block_width
        p_y = pos[1] // self.block_height
        i_x, i_y = pos[0] % self.block_width, pos[1] % self.block_height
        graphics = True
        original = self.parent.get_raw((p_x, p_y))
        if isinstance(original, Pixel):
            original = original.value
        elif isinstance(original, Sequence):
            original = original[0]
        if original is TRANSPARENT or original not in self.block_class:
            graphics = False
            original = EMPTY
        new_block = operation((i_x, i_y), original)
        return graphics, (p_x, p_y), new_block

    def set_at(self, pos):
        """Sets pixel at given coordinate

        Args:
          - pos (2-sequence): pixel coordinate

        To be used as a callback to ``.draw.set`` - but there are no drawbacks
        in being called directly.
        """
        _, gross_pos, new_block = self.operate(pos, self.block_class.set)
        self.parent[gross_pos] = new_block

    def reset_at(self, pos):
        """Resets pixel at given coordinate

        Args:
          - pos (2-sequence): pixel coordinate

        To be used as a callback to ``.draw.reset`` - but there are no drawbacks
        in being called directly.
        """
        _, gross_pos, new_block = self.operate(pos, self.block_class.reset)
        self.parent[gross_pos] = new_block

    def get_at(self, pos):
        """Queries pixel at given coordinate

        Args:
          - pos (2-sequence): pixel coordinate

        Returns:
           - True: pixel is set
           - False: pixel is not set
           - None: Character on Screen at given coordinates is not a block character of the class
                used as pixel-characters for this instance.
        """
        graphics, _, is_set = self.operate(pos, self.block_class.get_at)
        return is_set if graphics else None

    def at_parent(self, pos):
        """Get the equivalent, rounded down, coordinates, at the parent object.

        Args:
          - pos (2-sequence): screen coordinates, (0, 0) being the top-left corner.

        Returns:
          - V2 object with the equivalent object at the parent space.
        """
        return V2(pos[0] // self.block_width, pos[1] // self.block_height)

    def print_at(self, pos, text):
        """Positions the cursor and prints a text sequence

        [DEPRECATED] - use "at_parent" to get parent coordinates and other means to
            render text there.

        Args:
          - pos (2-sequence): screen coordinates, (0, 0) being the top-left corner.
          - txt: Text to render at position

        The text is printed as normal full-block characters. The method is given here
        just to enable using the same coordinate numbers to display other characters
        when drawing in high resolution.

        Context's direction is respected when printing
        """
        self.parent.print_at(self.at_parent(pos), text)


class Square(HighResBase):
    """Reimplements the sub-character block plotting to allow seamless full color in 1x2 resolution"""

    def __init__(self, parent, block_class=HalfChars, block_width=1, block_height=2):
        super().__init__(parent, block_class, block_width, block_height)
        self.PixelCls = parent.PixelCls

    def set_at(self, pos):
        """Sets pixel at given coordinate

        Args:
          - pos (2-sequence): pixel coordinate

        To be used as a callback to ``.draw.set`` - but there are no drawbacks
        in being called directly.
        """
        is_graphics, gross_pos, new_block = self.operate(pos, self.block_class.set)
        current = self.parent.PixelCls(*self.parent.get_raw(gross_pos))

        if new_block == HalfChars.FULL_BLOCK:
            if self.context.color == current.foreground:
                new_pixel = self.PixelCls(HalfChars.FULL_BLOCK, self.context.color, self.context.background, self.context.effects)
            elif current.foreground is DEFAULT_FG:
                new_block = HalfChars.UPPER_HALF_BLOCK if pos[1] % 2 == 1 else HalfChars.LOWER_HALF_BLOCK
                new_pixel = self.PixelCls(new_block, current.foreground, self.context.color, self.context.effects)
            else:
                new_block = HalfChars.UPPER_HALF_BLOCK if pos[1] % 2 == 0 else HalfChars.LOWER_HALF_BLOCK
                new_pixel = self.PixelCls(new_block, self.context.color, current.foreground, self.context.effects)
        elif current.value == HalfChars.EMPTY or not is_graphics:
            new_pixel = self.PixelCls(new_block, self.context.color, current.background, self.context.effects)
        else:  # implies  current.value == new_block and current.value in (HalfChars.UPPER_HALF_BLOCK, HalfChars.LOWER_HALF_BLOCK):
            new_pixel = current._replace(foreground=self.context.color, effects=self.context.effects)

        self.parent[gross_pos] = new_pixel

    def reset_at(self, pos):
        """Resets pixel at given coordinate

        Args:
          - pos (2-sequence): pixel coordinate

        To be used as a callback to ``.draw.reset`` - but there are no drawbacks
        in being called directly.
        """
        is_graphics, gross_pos, new_block = self.operate(pos, self.block_class.reset)
        current = self.parent.PixelCls(*self.parent.get_raw(gross_pos))

        if new_block == HalfChars.EMPTY:
            if self.context.background == current.background:
                new_pixel = self.PixelCls(HalfChars.EMPTY, self.context.color, self.context.background, self.context.effects)
            elif current.background is DEFAULT_BG:
                new_block = HalfChars.UPPER_HALF_BLOCK if pos[1] % 2 == 0 else HalfChars.LOWER_HALF_BLOCK
                new_pixel = self.PixelCls(new_block, self.context.background, current.background, self.context.effects)
            else:
                new_block = HalfChars.UPPER_HALF_BLOCK if pos[1] % 2 == 1 else HalfChars.LOWER_HALF_BLOCK
                new_pixel = self.PixelCls(new_block, current.background, self.context.background, self.context.effects)
        elif current.value == HalfChars.FULL_BLOCK:
            new_pixel = self.PixelCls(new_block, current.foreground, self.context.background, self.context.effects)
        else:  # implies  current.value == new_block and current.value in (HalfChars.UPPER_HALF_BLOCK, HalfChars.LOWER_HALF_BLOCK):
            new_pixel = current._replace(background=self.context.background, effects=self.context.effects)

        self.parent[gross_pos] = new_pixel

    def get_at(self, pos):
        """Queries pixel at given coordinate

        Args:
          - pos (2-sequence): pixel coordinate

        Returns:
           - True: pixel is set
           - False: pixel is not set
           - None: Character on Screen at given coordinates is not a block character of the class
                used as pixel-characters for this instance.
        """

        is_graphics, gross_pos, is_set = self.operate(pos, self.block_class.get_at)
        current = self.parent.get_raw(gross_pos)
        # foreground ...else... background
        return current[1] if is_set else current[2]


def HighRes(parent, block_class=BlockChars, block_width=2, block_height=2):
    """Factory method - uses specialized class if Square resolution for a shape supporting FG & BG is requested"""

    cap = parent.PixelCls.capabilities if hasattr(parent, "PixelCls") else None
    full_color = cap and cap.has_foreground and cap.has_background
    cls = Square if full_color and block_width == 1 and block_height == 2 else HighResBase
    return cls(parent, block_class, block_width, block_height)
