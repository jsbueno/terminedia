"""Terminedia is a library providing utilities to control and draw on the text terminal

Usage: import terminedia main classes and constants and control the terminal
is if it is a multi-functional canvas.
Drawing primitives that operate with block chars are provided, as well as
non-blocking keyboard reading.
"""

import array
import fcntl
import os
import sys
import threading
import time

from collections import defaultdict, namedtuple
from contextlib import contextmanager
from enum import Enum
from functools import lru_cache
from math import ceil
from pathlib import Path

from terminedia.keyboard import realtime_keyb, inkey, pause, KeyCodes
from terminedia.utils import V2, mirror_dict, Directions

try:
    from PIL import Image as PILImage
except ImportError:
    PILImage = None


__version__ = "0.3.dev0"
__author__ = "João S. O. Bueno"


#: Constant used as color to mean the default terminal foreground
#: (Currently all other color values should be RGB)
DEFAULT_FG = 0xffff
#: Constant used as color to mean the default terminal background
DEFAULT_BG = 0xfffe
#: Constant used as color to mean keep the current context colors
CONTEXT_COLORS = 0xfffd


class BlockChars_:
    """Used internaly to emulate pixel setting/resetting/reading inside 1/4 block characters

    Contains a listing and other mappings of all block characters used in order, so that
    bits in numbers from 0 to 15 will match the "pixels" on the corresponding block character.

    Although this class is purposed for internal use in the emulation of
    a higher resolution canvas, its functions can be used by any application
    that decides to manipulate block chars.

    The class itself is stateless, and it is used as a single-instance which
    uses the name :any:`BlockChars`. The instance is needed so that one can use the operator
    ``in`` to check if a character is a block-character.

    """
    EMPTY = " "
    QUADRANT_UPPER_LEFT = '\u2598'
    QUADRANT_UPPER_RIGHT = '\u259D'
    UPPER_HALF_BLOCK = '\u2580'
    QUADRANT_LOWER_LEFT = '\u2596'
    LEFT_HALF_BLOCK = '\u258C'
    QUADRANT_UPPER_RIGHT_AND_LOWER_LEFT = '\u259E'
    QUADRANT_UPPER_LEFT_AND_UPPER_RIGHT_AND_LOWER_LEFT = '\u259B'
    QUADRANT_LOWER_RIGHT = '\u2597'
    QUADRANT_UPPER_LEFT_AND_LOWER_RIGHT = '\u259A'
    RIGHT_HALF_BLOCK = '\u2590'
    QUADRANT_UPPER_LEFT_AND_UPPER_RIGHT_AND_LOWER_RIGHT = '\u259C'
    LOWER_HALF_BLOCK = '\u2584'
    QUADRANT_UPPER_LEFT_AND_LOWER_LEFT_AND_LOWER_RIGHT = '\u2599'
    QUADRANT_UPPER_RIGHT_AND_LOWER_LEFT_AND_LOWER_RIGHT = '\u259F'
    FULL_BLOCK = '\u2588'

    # This depends on Python 3.6+ ordered behavior for local namespaces and dicts:
    block_chars_by_name = {key: value for key, value in locals().items() if key.isupper()}
    block_chars_to_name = mirror_dict(block_chars_by_name)
    blocks_in_order = {i: value for i, value in enumerate(block_chars_by_name.values())}
    block_to_order = mirror_dict(blocks_in_order)

    def __contains__(self, char):
        """True if a char is a "pixel representing" block char"""
        return char in self.block_chars_to_name

    @classmethod
    def _op(cls, pos, data, operation):
        number = cls.block_to_order[data]
        index = 2 ** (pos[0] + 2 * pos[1])
        return operation(number, index)

    @classmethod
    def set(cls, pos, data):
        """"Sets" a pixel in a block character

        Args:
          - pos (2-sequence): coordinate of the pixel inside the character
            (0,0) is top-left corner, (1,1) bottom-right corner and so on)
          - data: initial character to be composed with the bit to be set. Use
            space ("\x20") to start with an empty block.

        """
        op = lambda n, index: n | index
        return cls.blocks_in_order[cls._op(pos, data, op)]

    @classmethod
    def reset(cls, pos, data):
        """"resets" a pixel in a block character

        Args:
          - pos (2-sequence): coordinate of the pixel inside the character
            (0,0) is top-left corner, (1,1) bottom-right corner and so on)
          - data: initial character to be composed with the bit to be reset.
        """
        op = lambda n, index: n & (0xf - index)
        return cls.blocks_in_order[cls._op(pos, data, op)]

    @classmethod
    def get_at(cls, pos, data):
        """Retrieves whether a pixel in a block character is set

        Args:
          - pos (2-sequence): The pixel coordinate
          - data (character): The character were to look at blocks.

        Raises KeyError if an invalid character is passed in "data".
        """
        op = lambda n, index: bool(n & index)
        return cls._op(pos, data, op)


#: :any:`BlockChars_` single instance: enables ``__contains__``:
BlockChars = BlockChars_()


class ScreenCommands:
    """Low level functions to execute ANSI-Sequence-related tasks on the terminal.

    Although not private, this class is meant to be used internally by the higher level
    :any:`Screen` and :any:`Drawing` classes. One might use these functions directly if
    there is no interest in the other functionalities of the library, though,
    or, to make use of a custom ANSI sequence which is not available in the higher level
    API.
    """
    last_pos = None

    def print(self, *args, sep='', end='', flush=True, count=0):
        """Inner print method

        Args:
          - \*args: strings to be joined by "sep" and printed
          - sep: Separator to join \*args
          - end: Sequence to print at end
          - flush: Whether to flush stdin file at end, defaults to ``True``
          - count: Retry counter - used to calculate delays on retries, or raise
            on max-retries exceeded (currently hardcoded to 10 atempts)

        Is used in place of normal Python's print, changing the defaults
        to values more suitable to the internal usage.
        Also, takes care of eventual blocking in stdout due to excess data -
        and implements a retry mechanism to mitigate that.
        """
        try:
            for arg in args:
                sys.stdout.write(arg)
                if sep:
                    sys.stdout.write(sep)
            if end:
                sys.stdout.write(end)
            if flush:
                sys.stdout.flush()
        except BlockingIOError:
            if count > 10:
                print("arrrrghhhh - stdout clogged out!!!", file=sys.stderr)
                raise
            time.sleep(0.002 * 2 ** count)
            self.print(*args, sep=sep, end=end, flush=flush, count=count + 1)

    def CSI(self, *args):
        """Writes a CSI command to the terminal

        Args:
          - \*args: Sequence of parameters to the command, including the last
              one that should be a letter specifying the command

        Just a fancy way to print the ANSI "CSI" (Control Sequence Introducer") commands
        These are commads stated with the "<ESC>[" sequence.

        Check https://en.wikipedia.org/wiki/ANSI_escape_code#CSI_sequences for available commands
        """
        command = args[-1]
        args = ';'.join(str(arg) for arg in args[:-1]) if args else ''
        self.print("\x1b[", args, command)

    def SGR(self, *args):
        """Writes a SGR command (Select Graphic Rendition)

        Args:
          - \*args: Sequence of parameters to the SGR command,

        This function calls .CSI with the command fixed as "m"
          which is "SGR".
        """
        self.CSI(*args, 'm')

    def clear(self):
        """Writes ANSI Sequence to clear the screen"""
        self.CSI(2, 'J')

    def cursor_hide(self):
        """Writes ANSI Sequence to hide the text cursor"""
        self.CSI('?25', 'l')

    def cursor_show(self):
        """Writes ANSI Sequence to show the text cursor"""
        self.CSI('?25', 'h')

    def moveto(self, pos):
        """Writes ANSI Sequence to position the text cursor

        Args:
          - pos (2-sequence): screen coordinates, (0, 0) being the top-left corner.

        Please note that ANSI commands count screen coordinates from 1,
        while in this project, coordinates start at 0 to conform
        to graphic display expected behaviors
        """
        if list(pos) == self.__class__.last_pos:
            return
        x, y = pos
        self.CSI(f'{y + 1};{x + 1}H')
        self.__class__.last_pos = list(pos)

    def print_at(self, pos, txt):
        """Positions the cursor and prints a text sequence

        Args:
          - pos (2-sequence): screen coordinates, (0, 0) being the top-left corner.
          - txt: Text to render at position

        There is an optimization that avoids re-issuing
        cursor-positioning ANSI sequences for repeated
        calls of this function - this uses a class
        attribute so that different Screen instances won't clash,
        but might yield concurrency problems if apropriate
        locks are not in place in concurrent code.
        """

        self.moveto(pos)
        self.print(txt)
        self.__class__.last_pos[0] += len(txt)

    @lru_cache()
    def _normalize_color(self, color):
        """Converts RGB colors to use 0-255 integers.

        Args:
          - color: Either a color constant or a 3-sequence,
              with float components on the range 0.0-1.0, or integer components
              in the 0-255 range.

        returns: Color constant, or 3-sequence normalized to 0-255 range.
        """
        if isinstance(color, int):
            return color
        if 0 <= color[0] < 1.0 or color[0] == 1.0 and all(c <= 1.0 for c in color[1:]):
            color = tuple(int(c * 255) for c in color)
        return color

    def reset_colors(self):
        """Writes ANSI sequence to reset terminal colors to the default"""
        self.SGR(0)

    def set_colors(self, foreground, background):
        """Sets foreground and background colors on the terminal
        foreground: the foreground color
        background: the background color
        """
        self.set_fg_color(foreground)
        self.set_bg_color(background)

    def set_fg_color(self, color):
        """Writes ANSI sequence to set the foreground color
        color: RGB  3-sequence (0.0-1.0 or 0-255 range) or color constant
        """
        if color == DEFAULT_FG:
            self.SGR(39)
        else:
            color = self._normalize_color(color)
            self.SGR(38, 2, *color)

    def set_bg_color(self, color):
        """Writes ANSI sequence to set the background color
        color: RGB  3-sequence (0.0-1.0 or 0-255 range) or color constant
        """
        if color == DEFAULT_BG:
            self.SGR(49)
        else:
            color = self._normalize_color(color)
            self.SGR(48, 2, *color)



class JournalingScreenCommands(ScreenCommands):
    """Internal use class to write ANSI-Sequence commands to the terminal

    This class implements a journaling technique to group commands to be
    sent to the display. While it exposes the same methods than the parent class,
    the "print_at", "set_foreground" and "set_background" methods can be used
    in a managed context to group all commands so that all writtings to
    the screen will be made in as few calls to stdin.write as possible.

    Although directly calling the methods in this class is not
    recomended when using the higher level classes,
    it can be used as a context manager to group drawing blocks
    to the screen - in a way similar to what is used to
    render an entire frame at once in a graphics display.

    For that purpose, use the instance of this class that is kept
    in the :any:`Screen.commands` attribute of the Screen class instance.
    (That is, one should use: ``with screen.commands:`` to start
    a block of graphics that should be rendered as fast as possible)

    When the context exits, writtings are made to the terminal
    to print all elements in a left-right, top-down order,
    regardless of the order in which they were drawn inside
    the context managed block.

    """

    def __init__(self):
        """__init__ initializes internal attributes"""
        self.in_block = 0
        self.current_color = DEFAULT_FG
        self.current_background = DEFAULT_BG
        self.current_pos = 0, 0

    def __enter__(self):
        """Enters a context where screen rights are collected together.

        These are yielded to the screen at once.
        This is written in a way that the contexts can be nested,
        so, if an inner method one is calling opens a
        context, one is free to open a broather context
        in an outer function - the graphics will just be rendered
        when the outer context is ended.
        """
        if self.in_block == 0:
            self.journal = {}
        self.tick = 0
        self.in_block += 1


    def _set(self, pos, char):
        """Internal function

        Args:
          - pos (2-sequence): coordinate where setting
          - char (strig of lenght 1): character to set

        Inside a managed context this is called to anotate the current color and position
        data to the internal Journal.
        """
        if not self.in_block:
            raise RuntimeError("Journal not open")
        self.journal.setdefault(pos, []).append((self.tick, char, self.current_color, self.current_background))
        self.tick += 1


    def __exit__(self, exc_name, traceback, frame):
        """Exists a managed context.

        If an exception took place, rendering is ignored. If it is an
        inner of a set of nested contexts, takes count of that.
        Otherwise renders the journaled commands to the terminal.
        """
        if exc_name:
            return

        self.in_block -= 1
        if self.in_block == 0:
            self.replay()

    def replay(self):
        """Renders the commands recorded to the terminal screen.

        This collects the last-writting in each screen position,
        groups same-color in consecutive left-to-right characters to avoid
        redundant color-setting sequences.

        It is called automatically on exiting a managed-context -
        but can be called manually to render partially whatever commands
        are recorded so far. The journal is not touched and
        can be further used inside the same context.
        """
        last_color = last_bg = None
        last_pos = None
        buffer = ""

        for pos in sorted(self.journal, key=lambda pos: (pos[1], pos[0])):
            tick, char, color, bg = self.journal[pos][-1]
            call = []
            if color != last_color:
                last_color = color
                call.append((self.set_fg_color, color))

            if bg != last_bg:
                last_bg = bg
                call.append((self.set_bg_color, bg))

            if pos != last_pos:
                last_pos = pos
                call.append((self.moveto, pos))

            if call:
                if buffer:
                    self.print(buffer)
                    buffer = ""
                for func, arg in call:
                    func(arg)
            buffer += char
            last_pos = pos[0] + 1, pos[1]

        if buffer:
            self.print(buffer)

    def print_at(self, pos, txt):
        """Positions the cursor and prints a text sequence

        Args:
          - pos (2-sequence): screen coordinates, (0, 0) being the top-left corner.
          - txt: Text to render at position

        All characters are logged into he journal if inside a managed block.
        """
        if not self.in_block:
            return super().print_at(pos, txt)
        for x, char in enumerate(txt, pos[0]):
            self._set((x, pos[1]), char)

    def set_fg_color(self, color):
        """Writes ANSI sequence to set the foreground color

        Args:
          - color (constant or 3-sequence): RGB color (0.0-1.0 or 0-255 range) or constant to set as fg color
        """
        if not self.in_block:
            super().set_fg_color(color)
        self.current_color = color

    def set_bg_color(self, color):
        """Writes ANSI sequence to set the background color

        Args:
          - color (constant or 3-sequence): RGB color (0.0-1.0 or 0-255 range) or constant to set as fg color
        """
        if not self.in_block:
            super().set_bg_color(color)
        self.current_background = color



class Drawing:
    """Drawing and rendering API

    An instance of this class is attached to :any:`Screen` instances as the :any:`Screen.draw` attribute.
    All context-related information is kept on the associanted screen instance,
    the public methods here issue pixel setting and resetting at the Screen -
    using that Screen's context colors and resolution.

    That is - the tipical usage for methods here will be ``screen.draw.line((0,0)-(50,20))``
    """

    def __init__(self, set_fn, reset_fn, size_fn, context):
        """Not intented to be instanced directly -

        Args:
          - set_fn (callable): function to set a pixl
          - reset_fn (callable): function to reset a pixel
          - size_fn (callable): function to retrieve the width and height of the output
          - context : namespace where screen attributes are set

        This takes note of the callback functions for
        screen-size, pixels set and reset and the drawing context.
        """
        self.set = set_fn
        self.reset = reset_fn
        self.size = property(size_fn)
        self.context = context

    def line(self, pos1, pos2, erase=False):
        """Draws a straight line connecting both coordinates.

        Args:
          - pos1 (2-tuple): starting coordinates
          - pos2 (2-tuple): ending coodinates
          - erase (bool): Whether to draw (set) or erase (reset) pixels.

        Public call to draw an arbitrary line using character blocks
        on the terminal.
        The color line is defined in the associated's screen context.color
        attribute. In the case of high-resolution drawing, the background color
        is also taken from the context.
        """

        op = self.reset if erase else self.set
        x1, y1 = pos1
        x2, y2 = pos2
        op(pos1)

        max_manh = max(abs(x2 - x1), abs(y2 - y1))
        if max_manh == 0:
            return
        step_x = (x2 - x1) / max_manh
        step_y = (y2 - y1) / max_manh
        total_manh = 0
        while total_manh < max_manh:
            x1 += step_x
            y1 += step_y
            total_manh += max(abs(step_x), abs(step_y))
            op((round(x1), round(y1)))

    def rect(self, pos1, pos2=(), *, rel=(), fill=False, erase=False):
        """Draws a rectangle

        Args:
          - pos1 (2-tuple): top-left coordinates
          - pos2 (2-tuple): bottom-right coodinates. If not given, pass "rel" instead
          - rel (2-tuple): (width, height) of rectangle. Ignored if "pos2" is given
          - fill (bool): Whether fill-in the rectangle, or only draw the outline. Defaults to False.
          - erase (bool): Whether to draw (set) or erase (reset) pixels.

        Public call to draw a rectangle using character blocks
        on the terminal.
        The color line is defined in the associated's screen context.color
        attribute. In the case of high-resolution drawing, the background color
        is also taken from the context.
        """
        if not pos2:
            if not rel:
                raise TypeError("Must have either two corners or 'rel' parameter")
            pos2 = pos1[0] + rel[0], pos1[1] + rel[1]
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


    def _link_prev(self, pos, i, limits, mask):
        if i < limits[0] - 1:
            for j in range(i, limits[0]):
                self.set((pos[0] + j, pos[1]))
                mask[j] = True
        elif i + 1 > limits[1]:
            for j in range(limits[1], i):
                self.set((pos[0] + j, pos[1]))
                mask[j] = True

    def ellipse(self, pos1, pos2, *, rel=(), fill=False):
        """Draws an ellipse

        Args:
          - pos1 (2-tuple): top-left coordinates of rectangle conataining ellipse
          - pos2 (2-tuple): bottom-right coodinates. If not given, pass "rel" instead
          - rel (2-tuple): (width, height) of rectangle. Ignored if "pos2" is given
          - fill (bool): Whether fill-in the rectangle, or only draw the outline. Defaults to False.

        Public call to draw an ellipse using character blocks
        on the terminal.
        The color line is defined in the associated's screen context.color
        attribute. In the case of high-resolution drawing, the background color
        is also taken from the context.
        """
        if not pos2:
            if not rel:
                raise TypeError("Must have either two corners or 'rel' parameter")
            pos2 = pos1[0] + rel[0], pos1[1] + rel[1]

        return self._empty_ellipse(pos1, pos2) if not fill else self._filled_ellipse(pos1, pos2)

    def _filled_ellipse(self, pos1, pos2):
        from math import sin, cos, asin

        x1, y1 = pos1
        x2, y2 = pos2

        x1, x2 = (x1, x2) if x1 <= x2 else (x2, x1)
        y1, y2 = (y1, y2) if y1 <= y2 else (y2, y1)

        cx, cy = x1 + (x2 - x1) / 2, y1 + (y2 - y1) / 2
        r1, r2 = x2 - cx, y2 - cy

        lx = x2 - x1 + 1

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
        count = 0
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
                step *= (1 - factor)
                factor *= 0.8
            elif x == ox and y == oy:
                t -= step
                step *= (1 + factor)
                factor *= 0.8
            else:
                factor = 0.25

            self.set((x, y))
            ox, oy = x, y


    def bezier(self, pos1, pos2, pos3, pos4):
        """Draws a bezier curve given the control points

        Args:
            pos1 (2-sequence): Fist control point
            pos2 (2-sequence): Second control point
            pos3 (2-sequence): Third control point
            pos4 (2-sequence): Fourth control point
        """
        pos1 = V2(pos1)
        pos2 = V2(pos2)
        pos3 = V2(pos3)
        pos4 = V2(pos4)
        x, y = pos1

        t = 0
        step = 1 / (abs(pos4-pos3) + abs(pos3 - pos2) + abs(pos2- pos1))
        self.set((x, y))
        ox, oy = x, y
        while t <= 1.0:

            x, y = pos1 * (1 - t) ** 3 + pos2 * 3 * (1 - t) ** 2 * t + pos3 * 3 * (1 - t) * t ** 2 + pos4 * t ** 3

            self.set((round(x), round(y)))
            t += step


    def blit(self, pos, data, color_map=None, erase=False):
        """Blits a blocky image in the associated screen at POS

        Args:
          - pos (2-tuple): top-left corner of the image
          - shape (Shape/string/list): Shape object or multi-line string or list of strings with shape to be drawn
          - color_map (Optional mapping): palette mapping chracters in shape to a color
          - erase (bool): if True white-spaces are erased, instead of being ignored. Default is False.

        Shapes return specialized Pixel classes when iterated upon -
        what is set on the screen depends on the Pixel returned.
        As of version 0.3dev, Shape class returns a pixel
        that has a True or False value and a foreground color (or no color) -
        support for other Pixel capabilities is not yet implemented.

        """

        original_color = self.context.color
        if isinstance(data, (str, list)):
            shape=PalletedShape(data, color_map)
        elif isinstance(data, Shape):
            shape = data

        pos = V2(pos)

        for pixel_pos, pixel in shape:
            if pixel.capabilities.value_type == bool:
                pixel_function = self.set if pixel.value else self.reset
                if not pixel.value and not erase:
                    continue
            else:
                pass
                # TODO
                # pixel_function =  self.print_at(...)
            if pixel.capabilities.has_foreground:
                if pixel.foreground == CONTEXT_COLORS:
                    self.context.color = original_color
                else:
                    self.context.color = pixel.foreground
            pixel_function(pos + pixel_pos)


class HighRes:
    """ Provides a seamless mechanism to draw with 1/4 character block "pixels".

    This class is meant to be used as an instance associated to an :any:`Screen` instance,
    at the :any:`Screen.high` namespace. It further associates a :any:`Drawing` instance
    as ``screen.high.draw`` which exposes drawing primitives that will use
    the 1/4 character pixel as a unit.

    Keep in mind that while it is possible to emulate the higher resolution
    pixels, screen colors are limited to character positions, so color
    on these pixels will "leak" to their block. (Users familiar
    with the vintage 8 bit ZX-Spectrum should feel at home)

    This class should not be instanced or used directly - instead, call the ``Drawing`` methods
    or the ``get_at``, ``get_size`` and ``print_at`` methods in the ``HighRes`` instance created
    automatically for a Screen instance.

    """

    def __init__(self, parent):
        """Sets instance attributes"""
        self.parent = parent
        self.draw = Drawing(self.set_at, self.reset_at, self.get_size, self.parent.context)
        self.context = parent.context

    def get_size(self):
        """Returns the width and height available at high-resolution based on parent's Screen size"""
        w, h = self.parent.get_size()
        return V2(w * 2, h * 2)

    def operate(self, pos, operation):
        """Internal -

        Common code to calculate the coordinates and get/reset/query a 1/4 character pixel.
        Call  :any:`HighRes.set_at`, :any:`HighRes.reset_at` or :any:`HighRes.get_at` instead.
        """
        p_x = pos[0] // 2
        p_y = pos[1] // 2
        i_x, i_y = pos[0] % 2, pos[1] % 2
        graphics = True
        original = self.parent[p_x, p_y]
        if original not in BlockChars:
            graphics = False
            original = " "
        new_block = operation((i_x, i_y), original)
        return graphics, (p_x, p_y), new_block

    def set_at(self, pos):
        """Sets pixel at given coordinate

        Args:
          - pos (2-sequence): pixel coordinate

        To be used as a callback to ``.draw.set`` - but there are no drawbacks
        in being called directly.
        """
        _, gross_pos, new_block = self.operate(pos, BlockChars.set)
        self.parent[gross_pos] = new_block

    def reset_at(self, pos):
        """Resets pixel at given coordinate

        Args:
          - pos (2-sequence): pixel coordinate

        To be used as a callback to ``.draw.reset`` - but there are no drawbacks
        in being called directly.
        """
        _, gross_pos, new_block = self.operate(pos, BlockChars.reset)
        self.parent[gross_pos] = new_block

    def get_at(self, pos):
        """Queries pixel at given coordinate

        Args:
          - pos (2-sequence): pixel coordinate

        Returns:
           - True: pixel is set
           - False: pixel is not set
           - None: Character on Screen at given coordinates is not a block character and can't be
               mapped to 1/4 character pixels.
        """
        graphics, _, is_set = self.operate(pos, BlockChars.get_at)
        return is_set if graphics else None

    def print_at(self, pos, text):
        """Positions the cursor and prints a text sequence

        Args:
          - pos (2-sequence): screen coordinates, (0, 0) being the top-left corner.
          - txt: Text to render at position

        The text is printed as normal full-block characters. The method is given here
        just to enable using the same coordinate numbers to display other characters
        when drawing in high resolution.

        Context's direction is respected when printing
        """
        pos = pos[0] // 2, pos[1] // 2
        self.parent.print_at(pos, text)


class Screen:
    """Canvas class for terminal drawing.

    This is the main class on Terminedia library - methods and associated instances here
    should be used to do all screen rendering and drawing save for low-level work.

    Use this as a context manager inside which the screen is active;

    For drawing primitives using full-block chars, use the instance's
    :any:`Screen.draw`, which contains a :any:`Drawing` instance. Terminal context colors
    and other attributes can be set in a thread-safe way on the
    ``screen.context`` namespace.

    To draw and position characters using 1/4 character high resolution,
    use the attributes and methods available at :any:`Screen.high`.
    (High resolution drawing methods are available at ``screen.high.draw``)

    Besides the available methods and associated instances, screen contents
    can be set and read by using the Screen instance as a 2-dimensional mapping.
    For example, ``screen[10, 10] = "A"`` will set the character on that position.

    Args:
      - size (optional 2-sequence): Screen size in blocks. If not given, terminal size is queried automatically.
        This does not resize the actual terminal - a smaller area is available to the methods instead.
        If given size is larger than the actual terminal, mayhen ensues.
      - clear_screen (bool): Whether to clear the terminal and hide cursor when entering the screen. Defaults to True.

    """

    #: Lock to avoid ANSI sequence mangling if used in multi-threading
    lock = threading.Lock()

    #: Internal: tracks last used background attribute to avoid mangling and enable optimizations
    last_background = None
    #: Internal: tracks last used foreground attribute to avoid mangling and enable optimizations
    last_color = None

    def __init__(self, size=(), clear_screen=True):
        if not size:
            #: Set in runtime to a method to retrieve the screen width, height.
            #: The class is **not** aware of terminal resizings while running, though.
            self.get_size = lambda: V2(os.get_terminal_size())
            size = self.get_size()
        else:
            self.get_size = lambda: V2(size)

        #: Namespace to configure drawing and printing color and other parameters.
        #: Currently, the attributes that are used from here are
        #: ``color``, ``background`` and ``direction`` (which have to be set to one
        #: of the values in :any:`Directions`.
        self.context = threading.local()

        #: Namespace for drawing methods, containing an instance of the :any:`Drawing` class
        self.draw = Drawing(self.set_at, self.reset_at, self.get_size, self.context)
        self.width, self.height = self.size = size

        #: Namespace to allow high-resolution drawing using a :any:`HighRes` instance
        #: One should either use the public methods in HighRes or the methods on the
        #: :any:`Drawing` instance at ``Screen.high.draw`` to do 1/4 block pixel
        #: manipulation.
        self.high = HighRes(self)

        #: Namespace for low-level Terminal commands, an instance of :any:`JournalingScreenCommands`.
        #: This attribute can be used as a context manager to group
        #: various screen operations in a single block that is rendered at once.
        self.commands = JournalingScreenCommands()
        self.clear_screen = clear_screen

    def __enter__(self):
        """Enters a fresh screen context"""
        self.clear(self.clear_screen)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Leaves the screen context and reset terminal colors."""
        if self.clear_screen:
            self.commands.clear()
            self.commands.moveto((0,0))
        self.commands.cursor_show()
        self.commands.reset_colors()

    def clear(self, wet_run=True):
        """Resets internal data, context parameters and clears the screen

        Args:
          - wet_run (bool): Whether to physically clear the screen or not

        Resets internal data and context parameters. The "self.data" and "self.color_data"
        structures are where the current character and attributes for each position are kept
        as characters actually just printed on the terminal can't be "read" back.
        Context foreground, background and direction are reset.

        In default operation, commands to clear the actual terminal and hide the cursor
        is also issued - the ``.clear_screen`` attribute controls that if ``.clear`` is being
        called as part of entering the screen context.

        """
        self.data = [" "] * self.width * self.height
        self.color_data = [(DEFAULT_FG, DEFAULT_BG)] * self.width * self.height
        self.context.color = DEFAULT_FG
        self.context.background = DEFAULT_BG
        self.context.direction = Directions.RIGHT
        self.__class__.last_color = None
        # To use when we allow custom chars along with blocks:
        # self.char_data = " " * self.width * self.height
        with self.lock:
            if wet_run:
                self.commands.clear()
            self.commands.cursor_hide()

    def set_at(self, pos, color=None):
        """Sets pixel at given coordinate

        Args:
          - pos (2-sequence): pixel coordinate

        To be used as a callback to ``.draw.set`` - but there are no drawbacks
        in being called directly.
        """

        if color:
            self.context.color = color
        self[pos] = BlockChars.FULL_BLOCK

    def reset_at(self, pos):
        """Resets pixel at given coordinate

        Args:
          - pos (2-sequence): pixel coordinate

        To be used as a callback to ``.draw.reset`` - but there are no drawbacks
        in being called directly.
        """

        self[pos] = " "

    def line_at(self, pos, length, sequence=BlockChars.FULL_BLOCK):
        """Renders a repeating character sequence of given length respecting the context.direction

        Args:
          - pos (2-sequence):  coordinates where to start drawing
          - length (int): length of character sequence to render
          - sequence (str): Text to render at position - defaults to full-block character

          Draws a vertical or horizontal line of characters, repeating the characteres
          of the sequence given, up to the specified length. Can be used to draw lines
          of aritrary characters or short words. The line directin is taken from the
          context's direction.
        """
        x, y = pos
        if not sequence:
            return
        for i, char in zip(range(length), sequence * (ceil(length / len(sequence)))):
            self[x, y] = char
            x += self.context.direction.value[0]
            y += self.context.direction.value[1]

    def print_at(self, pos, text):
        """Positions the cursor and prints a text sequence

        Args:
          - pos (2-sequence): screen coordinates, (0, 0) being the top-left corner.
          - txt: Text to render at position

        Context's direction is respected when printing
        """
        self.line_at(pos, len(text), sequence=text)

    def __getitem__(self, pos):
        """Retrieves character data at pos

        Args:
          - pos (2-sequence): coordinate to retrieve data from.
        """
        index = pos[0] + pos[1] * self.width
        if index < 0 or index >= len(self.data):
            return " "
        return self.data[index]

    def __setitem__(self, pos, value):
        """Writes character data at pos

        Args:
          - pos (2-sequence): coordinate where to set character
          - value (length 1 string): Character to set.

        This is mostly used internally by all other drawing and printing methods, although
        it can be used directly, by using Python's object-key notation with ``[ ]`` and assignment.
        The thing to have in mind is that all text or graphics that go to the terminal *is
        be directed through this method* - it is a "single point" where all data is
        sent, and this enabled keeping an in memory copy of the data that is printed
        at the terminal, a series of optimizations by not re-issuing color-change
        commands for each character printed, and finally some block-locking which enables
        the library to work even in multi-threaded concurrent code drawing at once
        to the terminal.

        """
        index = pos[0] + pos[1] * self.width
        if index < 0 or index >= len(self.data):
            return
        self.data[index] = value

        cls = self.__class__
        with self.lock:
            update_colors =  cls.last_color != self.context.color or cls.last_background != self.context.background
            colors = self.context.color, self.context.background
            self.color_data[index] = colors
            if update_colors:
                self.commands.set_colors(*colors)
                cls.last_color = self.context.color
                cls.last_background = self.context.background
            self.commands.print_at(pos, value)


class Context:
    """Context manager for :any:`Screen` context attributes (Pun not intended)

    Args:
      - screen (Screen): The screen where to operate

    Kwargs:
      should contain desired temporary attributes:

      - color: color special value or RGB sequence for foreground color - either int 0-255  or float 0-1 based.
      - background: color special value or RGB sequence sequence for background color
      - direction: terminedia.Directions Enum value with writting direction

    Provides a practical way for a sub-routine to draw things to the screen without messing with the
    callee's expected drawing context. Otherwise one would have to manually save and restore
    the context colors for each operation.  When entering this context, the original screen context
    is returned - changes made to it will be reverted when exiting.

    """
    SENTINEL = object()

    def __init__(self, screen, **kwargs):
        """Sets internal attributes"""
        self.screen = screen
        self.attrs = kwargs

    def __enter__(self):
        """Saves current screen context, sets new values and returns the context itself

        The returned context object can be safelly manipulated inside the block
        """
        self.original_values = {key:getattr(self.screen.context, key) for key in dir(self.screen.context) if not key.startswith("_")}
        for key, value in self.attrs.items():
            setattr(self.screen.context, key, value)
        return self.screen.context

    def __exit__(self, exc_name, traceback, frame):
        """Restores saved and previously not set context parameters"""
        for key, value in self.original_values.items():
            if value is self.SENTINEL:
                continue
            setattr(self.screen.context, key, value)
        for key in dir(self.screen.context):
            if not key.startswith("_") and not key in self.original_values:
                delattr(self.screen.context, key)


#class Color:
    #__slots__ = "r", "g", "b", "alpha"
    #def __init__(self, r, g=None, b=None, alpha=1.0):
        #self.r = r
        #self.g = g
        #self.b = b
        #self.alpha = alpha

    #def __repr__(self):
        #if self.g is None:
            #return f"Color(self.r)"
        #return f"Color(self.r, self.g, self.b, self.alpha"


PixelClasses = {}

pixel_capabilities = namedtuple("pixel_capabilities", "value_type has_foreground has_background has_text_attributes")

def pixel_factory(value_type=str, has_foreground=True, has_background=False, has_text_effects=False):
    """Returns a custom pixel class with specified capabilities

    Args:
        value_type(str or bool): Data type returned by the pixel
        has_foreground (bool): Whether pixel has a foreground color
        has_background (bool): Whether pixel has a background color
        has_text_effects (bool): Whether pixel has text-attribute flags

    Created pixel classes or instances are not intended to be directly manipulated -
    instead, they are just a way to convey information from internal images/shapes
    to methods that will draw then.
    """

    capabilities = pixel_capabilities(value_type, has_foreground, has_background, has_text_effects)
    if capabilities in PixelClasses:
        Pixel = PixelClasses[capabilities]
    else:
        pixel_tuple = namedtuple(
            "PixelBase",
            (
                ("value", ) +
                (("foreground", ) if has_foreground else () ) +
                (("background", ) if has_background else () ) +
                (("text_effects", ) if has_text_effects else () )
            ),
        )

        def __repr__(self):
            return "Pixel({})".format(", ".join(
                f"{field}={getattr(self, field)}" for field in pixel_tuple._fields
            ))

        Pixel = type(
            "Pixel",
            (pixel_tuple,),
            {
                "capabilities": capabilities,
                "__repr__": __repr__,
                "__slots__": (),
            }
        )


        @property
        def value(self):
            value = super(Pixel, self).value
            return (value not in (" .")) if value_type is bool and isinstance(value, str) else value_type(value)

        Pixel.value = value

        PixelClasses[capabilities] = Pixel

    return Pixel


class Shape:
    """'Shape' is intended to represent blocks of colors/backgrounds and characters
    to be applied in a rectangular area of the terminal. In this sense, it is
    more complicated than an "Image" that just care about a foreground color
    and alpha value for each pixel position.

    This is going to be implemented gradually - the first use case
    is a plain old "image" - the capability of including specific characters
    instead of blocks of solid color should be available later as
    subclasses of Shape.

    """

    # this data is to be found into the PixelCls.capabilities

    #foreground = False
    #background = False
    #arbitrary_chars = False
    #character_properties = False  # FUTURE: support for bold, blink, underline...

    PixelCls = pixel_factory(bool)
    def __init__(self, data, color_map=None):
        raise NotImplementedError("This is meant as an abstract Shape class")

    def get_raw(self, pos):
        return self.data[pos[1] * self.width + pos[0]]

    def __getitem__(self, pos):
        """Values for each pixel are: character, fg_color, bg_color, text_attributes.
        """
        raise NotImplementedError("This is meant as an abstract Shape class")


    def __setitem__(self, pos, value):
        """

        Values for each pixel are: character, fg_color, bg_color
        """
        raise NotImplementedError("This is meant as an abstract Shape class")

    def __iter__(self):
        """Iterates over all pixels in Shape


        For each pixel in the image, returns its position,
        its value, the foreground color, background color, and character_effects byte
        """
        for x in range(self.width):
            for y in range(self.height):
                pos = V2(x, y)
                yield (pos, self[pos])


class ValueShape(Shape):

    PixelCls = pixel_factory(bool, has_foreground=True)

    def __init__(self, data, color_map=None, **kwargs):

        self.kwargs = kwargs
        # TODO: make color_map work as a to-pixel pallete infornmation
        # to L or I images - not only providing a color palette,
        # but also enabbling an "palette color to character" mapping.
        self.color_map = color_map
        if isinstance(data, (Path, str)) or hasattr(data, "read"):
            self.load_file(data)
            return
        raise NotImplementedError(f"Can't load shape from {type(data).__name__}")

    def load_file(self, file_or_path):
        raise NotImplementedError()


    def __getitem__(self, pos):
        """Composes a Pixel object for the given coordinates.
        """
        color = self.get_raw(pos)

        return self.PixelCls(True, color)


    def __setitem__(self, pos, value):
        """
        Values set for each pixel are 3-sequences with an RGB color value
        """
        self.data[pos[1] * self.width + pos[0]] = value


class PGMShape(ValueShape):

    PixelCls = pixel_factory(bool, has_foreground=True)

    def load_file(self, file_or_path):
        if not hasattr(file_or_path, "read"):
            file = open(file_or_path, "rb")
        else:
            file = file_or_path
        raw_data = file.read()
        if raw_data[0] == ord(b"P") and raw_data[2] in b"\r\n":
            return self._decode_pnm(raw_data)
        raise NotImplementedError("File format not supported. Try installing 'Pillow' ")


    def _decode_pnm(self, data):
        headers = []
        header_counter = 0
        offset = 0
        while True:
            line_end = data.find(b"\n", offset)
            line = data[offset: line_end + 1]
            offset = line_end + 1
            if line.strip().startswith(b"#"):
                continue
            headers.append(line.strip())
            header_counter += 1
            if header_counter == 3:
                break
        type_, size, max_value = headers

        size=V2(*map(int, size.split()))
        max_value = int(max_value)

        self.width, self.height = size

        type_num = int(type_[1:2])
        if type_num == 2:
            # ASCII encoding, monochronme file
            ascii, values_per_pixel = True, 1
        elif type_num == 3:
            ascii, values_per_pixel = True, 3
        elif type_num == 5:
            ascii, values_per_pixel = False, 1
        elif type_num == 6:
            ascii, values_per_pixel = False, 3
        else:
            raise NotImplementedError(f"File not supported. PNM with magic number: {type_.decode!r}")

        data = data[offset:]
        if ascii:
            data = [int(v) for v in data.split()]
        if len(data) != size.x * size.y * values_per_pixel:
            sys.stderr.write("Warning: malformed PNM file. Trying to continue anyway\n")

        data = [value / max_value for value in data]
        if values_per_pixel == 1:
            data = [(value, value, value) for value in data]
        else:
            data = [tuple(data[i: i + 3]) for i in range(0, len(data), 3)]
        self.data = data


class ImageShape(ValueShape):

    PixelCls = pixel_factory(bool, has_foreground=True)


    def load_file(self, file_or_path):
        if isinstance(file_or_path, PILImage.Image):
            img = file_or_path
        else:
            img = PILImage.open(file_or_path)
        if self.kwargs.get("auto_scale", True):
            scr = self.kwargs.get("screen", None)
            pixel_ratio = self.kwargs.get("pixel_ratio", 2)

            size = V2(scr.get_size() if scr else (80, 12))
            img_size = V2(img.width, img.height)
            if size.x < img_size.x or size.y < img_size.y:
                ratio_x = size.x / img_size.x
                ratio_y = (size.y / img_size.y) * pixel_ratio
                if ratio_x > ratio_y:
                    size = V2(size.x, img_size.y * ratio_x / pixel_ratio)
                else:
                    size = V2(img_size * ratio_y, size.y / pixel_ratio)

                img = img.resize(size.as_int, PILImage.BICUBIC)

        self.width, self.height = img.width, img.height

        if img.mode in ("L", "P", "I"):
            img = img.convert("RGB")
        elif img.mode in ("LA", "PA"):
            img = img.convert("RGBA")
        self.data = img


    def get_raw(self, pos):
        return self.data.getpixel(pos)

    def __setitem__(self, pos, value):
        """
        Values set for each pixel are 3-sequences with an RGB color value
        """
        self.data.putpixel(value)


class PalletedShape(Shape):
    """'Shape' class intended to represent images, using a color-map to map characters to block colors.

    Args:
      - data (multiline string or list of strings): character map to be used as pixels
      - color_map (optional mapping): maps characters to RGB colors.
    This class have no special per pixel values for background or character - each
    block position will read as "False" or "True" depending only on the
    underlying character in the input data being space (0x20) or any other thing.
    """

    foreground = True
    background = False
    arbitrary_chars = False
    text_effects = False  # FUTURE: support for bold, blink, underline...

    PixelCls = pixel_factory(bool, has_foreground=True)

    def __init__(self, data, color_map=None):
        if isinstance(data, (str, list)):
            self.load_paletted(data, color_map)
            return
        elif isinstance(data, Path) or hasattr(data, "read"):
            self.load_file(data)
            return
        raise NotImplementedError(f"Can't load shape from {type(data).__name__}")

    def load_paletted(self, data, color_map):
        if isinstance(data, str):
            data = data.split("\n")
        self.width = max(len(line) for line in data)
        self.height = len(data)
        self.color_map = color_map
        if not color_map:
            self.PixelCls = pixel_factory(bool, has_foreground=False)
        self.data = [" "] * self.width * self.height

        for y, line in enumerate(data):
            for x in range(self.width):
                char = line[x] if x < len(line) else " "
                # For string-based shapes, '.' is considered
                # as whitespace - this allows multiline
                # strings defining shapes that otherwise would
                # be distorted by program editor trailing space removal.
                if char == ".":
                    char = " "
                self[x, y] = char


    def get_raw(self, pos):
        return self.data[pos[1] * self.width + pos[0]]


    def __getitem__(self, pos):
        """Values for each pixel are: character, fg_color, bg_color, text_attributes.
        """
        char = self.get_raw(pos)
        if self.color_map:
            foreground_arg = (self.color_map.get(char, DEFAULT_FG),)
        else:
            foreground_arg = ()

        return self.PixelCls(char, *foreground_arg)

    def __setitem__(self, pos, value):
        """
        Values set for each pixel are: character - only spaces (0x20) or "non-spaces" are
        taken into account for PalletedShape
        """
        self.data[pos[1] * self.width + pos[0]] = value


def shape(data, color_map=None, **kwargs):


    """Factory for shape objects

    Args:
      - data (Filepath to image, open file, image data as text or list of strings)
      - color_map (optional mapping): color map to be used for the image - mapping characters to RGB colors.
      - **kwargs: parameters passed transparently to the selected shape class

    Based on inferences on the data attribute, selects
    the appropriate Shape subclass to handle the "data" attribute
    as a pattern to be blitted on Screen instances. That is:
    given a string without newlines, it is interpreted as a
    filepath, and if PIL is installd, an RGB "ImageShape"
    class is used to read the image data. If text with "\n"
    is passed in, an PalletedShape is used to directly use
    the passed data as pixels.

    Returns an instance of the selected class with the data set.


    """
    if isinstance(data, str) and not "\n" in data or isinstance(data, Path) or hasattr(data, "read"):
        if hasattr(data, "read"):
            name = Path(getattr(data, "name", "stream"))
        else:
            name = Path(data)
        if not PILImage or name.suffix.strip(".").lower() in "pnm ppm pgm":
            cls = PGMShape
        else:
            cls = ImageShape
    elif PILImage and isinstance(data, PILImage.Image):
        cls = ImageShape
    elif isinstance(data, (list, str)):
        cls = PalletedShape
    elif isinstance(data, Shape):
        return data
    else:
        raise NotImplementedError("Could not pick a Shape class for given arguments!")
    return cls(data, color_map, **kwargs)


shape1 = """\
           .
     *     .
    * *    .
   ** **   .
  *** ***  .
 ********* .
           .
"""

shape2 = """\
                  .
   *    **    *   .
  **   ****   **  .
 **   **##**   ** .
 **   **##**   ** .
 **   **##**   ** .
 **************** .
 **************** .
   !!   !!   !!   .
   !!   !!   !!   .
  %  % %  % %  %  .
                   .
"""

c_map = {
    '*': DEFAULT_FG,
    '#': (.5, 0.8, 0.8),
    '!': (1, 0, 0),
    '%': (1, 0.7, 0),
}


def main():
    """Temporary main function to show some capabilities and perform testing.

    Check the "examples/" folder in the repository at
    https://github.com/jsbueno/terminedia for more examples.
    """
    with realtime_keyb(), Screen() as scr:

        factor = 2
        x = (scr.high.get_size()[0] // 2 - 13)
        x = x - x % factor
        y = 0
        K = KeyCodes
        mode = 0
        while True:
            key = inkey()
            if key == '\x1b':
                break

            with scr.commands:
                scr.high.draw.rect((x, y), rel=(26, 14), erase=True)


                if mode == 0:
                    y += factor

                    if y >= scr.high.get_size()[1] - 17:
                        mode = 1

                if mode == 1:
                    x -= factor
                    if x <= 0:
                        break


                #x += factor * ((key == K.RIGHT) - (key == K.LEFT))
                #y += factor * ((key == K.DOWN) - (key == K.UP))

                scr.high.draw.blit((x, y), shape2, color_map=c_map)

            time.sleep(1/30)



if __name__ == "__main__":
    #testkeys()
    main()

# Future chars to acomodate in extended drawing modes:
"""
U+25E2	◢	e2 97 a2	BLACK LOWER RIGHT TRIANGLE
U+25E3	◣	e2 97 a3	BLACK LOWER LEFT TRIANGLE
U+25E4	◤	e2 97 a4	BLACK UPPER LEFT TRIANGLE
U+25E5	◥	e2 97 a5	BLACK UPPER RIGHT TRIANGLE
"""

a = "  ◢◣◤◥"
a = "◢◣◤◥"
