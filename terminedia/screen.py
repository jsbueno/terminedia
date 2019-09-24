import logging
import os
import threading
from math import ceil

import terminedia.text
from terminedia.utils import V2, init_context_for_thread
from terminedia.terminal import JournalingScreenCommands
from terminedia.values import BlockChars, DEFAULT_BG, DEFAULT_FG, CONTEXT_COLORS, Effects, Directions
from terminedia.drawing import Drawing, HighRes
from terminedia.image import Pixel, FullShape

logger = logging.getLogger(__name__)

_REPLAY = object()

class Screen:
    """Canvas class for terminal drawing.

    This is the main class to interact with the terminal on Terminedia
    library - methods and associated instances here
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
    #: Internal: tracks last used effects attribute to avoid mangling and enable optimizations
    last_effects = None

    def __init__(self, size=(), clear_screen=True):
        if not size:
            #: Set in runtime to a method to retrieve the screen width, height.
            #: The class is **not** aware of terminal resizings while running, though.
            self.get_size = lambda: V2(os.get_terminal_size())
            try:
                size = self.get_size()
            except OSError as error:
                if error.errno == 25:
                    logger.error("This terminal type does not allow guessing screen size."
                        "Pass an explicit (cols, rows) size when instantiating {self.__class__}")
                raise
        else:
            self.get_size = lambda: V2(size)

        #: Namespace to configure drawing and printing color and other parameters.
        #: Currently, the attributes that are used from here are
        #: ``color``, ``background``, ``direction``, ``effects`` and ``char``.
        self.context = threading.local()

        #: Namespace for drawing methods, containing an instance of the :any:`Drawing` class
        self.draw = Drawing(self.set_at, self.reset_at, self.get_size, self.context)
        self.width, self.height = self.size = size

        #: Namespace to allow high-resolution drawing using a :any:`HighRes` instance
        #: One should either use the public methods in HighRes or the methods on the
        #: :any:`Drawing` instance at ``Screen.high.draw`` to do 1/4 block pixel
        #: manipulation.
        self.high = HighRes(self)

        self.text = terminedia.text.Text(self)

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
            self.commands.moveto((0, 0))
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
        init_context_for_thread(self.context)
        self.data = FullShape.new((self.width, self.height))
        self.data.context = self.context
        self.context.last_pos = V2(0,0)
        self.__class__.last_color = None
        self.__class__.last_background = None
        # To use when we allow custom chars along with blocks:
        # self.char_data = " " * self.width * self.height
        with self.lock:
            if wet_run:
                self.commands.clear()
            self.commands.cursor_hide()

    def set_at(self, pos, pixel=None):
        """Sets pixel at given coordinate

        Args:
          - pos (2-sequence): pixel coordinate
          - pixel (Optional[Pixel]): sets the context values according to pixel attributes prior to printing

        To be used as a callback to ``.draw.set`` - but there are no drawbacks
        in being called directly.
        """
        if pixel is not None:
            cap = pixel.capabilities
            char = pixel.value if issubclass(cap.value_type, str) else self.context.char
            if issubclass(cap.value_type, bool) and not pixel.value:
                char = BlockChars.EMPTY  # Plain old space
            for attr in ("foreground", "background", "effects"):
                if getattr(cap, "has_" + attr):
                    value = getattr(pixel, attr)
                    if value == CONTEXT_COLORS:
                        if attr == "foreground":
                            value = self.context.color_stack[-1]
                        elif attr == "background":
                            value = self.context.background_stack[-1]

                    setattr(self.context, attr if attr != "foreground" else "color", value)
        else:
            char = self.context.char

        self[pos] = char

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
            x += self.context.direction[0]
            y += self.context.direction[1]

    def print_at(self, pos, text):
        """Positions the cursor and prints a text sequence

        Args:
          - pos (2-sequence): screen coordinates, (0, 0) being the top-left corner.
          - txt: Text to render at position

        Context's direction is respected when printing
        """
        self.line_at(pos, len(text), sequence=text)

    def print(self, text):
        """Prints text picking at the last position that were printed to."""
        pos  = self.context.last_pos + self.context.direction.value
        self.print_at(pos, text)

    def __getitem__(self, pos):
        """Retrieves character data at pos

        Args:
          - pos (2-sequence): coordinate to retrieve data from.
        """
        return self.data[pos].value
        #if value[0] == CONTEXT_COLORS: value[0] = self.context.color
        #if value[1] == CONTEXT_COLORS: value[1] = self.context.background
        ## FIXME: 'CONTEXT_COLORS' may clash with a effects flag combination in the future.
        #if value[2] == CONTEXT_COLORS: value[2] = self.context.effects


    def __setitem__(self, pos, value):
        """Writes character data at pos

        Args:
          - pos (2-sequence): coordinate where to set character
          - value (length 1 string): Character to set.

        This is mostly used internally by all other drawing and printing methods, although
        it can be used directly, by using Python's object-key notation with ``[ ]`` and assignment.
        The thing to have in mind is that all text or graphics that go to the terminal *are
        directed through this method* - it is a "single point" where all data is
        sent, and this enabled keeping an in memory copy of the data that is printed
        at the terminal, a series of optimizations by not re-issuing color-change
        commands for each character printed, and finally some block-locking which enables
        the library to work even in multi-threaded concurrent code drawing at once
        to the terminal.

        """

        cls = self.__class__
        with self.lock:
            # Force underlying shape machinnery to apply context attributes and transformations:
            if value != _REPLAY:
                self.data[pos] = value
            pixel = self.data[pos]

            update_colors = (
                cls.last_color != pixel.foreground or
                cls.last_background != pixel.background or
                cls.last_effects != pixel.effects
            )
            if update_colors:
                colors = pixel.foreground, pixel.background, pixel.effects
                self.commands.set_colors(*colors)
                cls.last_color = pixel.foreground
                cls.last_background = pixel.background
                cls.last_effects = pixel.effects
            self.commands.print_at(pos, pixel.value)
            self.context.last_pos = V2(pos)

    def update(self, pos1=None, pos2=None):
        if pos1 == None:
            pos1 = (0, 0)
        if pos2 == None:
            pos2 = (self.width, self.height)
        pos1 = V2(pos1)
        pos2 = V2(pos2)
        with self.commands:
            for y in range(pos1.y, pos2.y):
                for x in range(pos1.x, pos2.x):
                    self[x, y] = _REPLAY


class Context:
    """Context manager for :any:`Screen` context attributes (Pun not intended)

    Args:
      - screen (Screen): The screen where to operate

    Kwargs:
      should contain desired temporary attributes:

      - color: color special value or RGB sequence for foreground color - either int 0-255  or float 0-1 based.
      - background: color special value or RGB sequence sequence for background color
      - direction: terminedia.Directions Enum value with writting direction
      - effects: terminedia.Effects Enum value with combination of text effects
      - char: Char to be plotted when setting a single color.

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
        self.original_values = {key:getattr(self.screen.context, key)
                                    for key in dir(self.screen.context) if not key.startswith("_")}
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
            if not key.startswith("_") and key not in self.original_values:
                delattr(self.screen.context, key)
