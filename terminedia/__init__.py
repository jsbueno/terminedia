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
from terminedia.utils import V2, Directions
from terminedia.terminal import ScreenCommands, JournalingScreenCommands
from terminedia.values import BlockChars, DEFAULT_BG, DEFAULT_FG, CONTEXT_COLORS
from terminedia.drawing import Drawing, HighRes
from terminedia.image import shape, Shape, PalletedShape


__version__ = "0.3.dev0"
__author__ = "João S. O. Bueno"


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
        directed through this method* - it is a "single point" where all data is
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
