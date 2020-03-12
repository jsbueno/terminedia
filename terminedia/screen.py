import logging
import os
import threading
import time
from math import ceil

import terminedia.text
from terminedia.contexts import Context
from terminedia.utils import contextkwords, V2, Rect, tick_forward, LazyBindProperty
from terminedia.subpixels import BrailleChars, HalfChars
from terminedia.values import (
    CONTINUATION,
    DEFAULT_BG,
    DEFAULT_FG,
    CONTEXT_COLORS,
    Directions,
    EMPTY,
    Effects,
    FULL_BLOCK,
    TRANSPARENT
)
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

    #: Instance contaning a mirror of the screen contents and attributes.
    #: All Screen drawing attributes are mirrored in it, but it can
    #: be updated independently and blitted to the terminal
    #: later by calling Screen.update.
    data: FullShape
    #: Lock to avoid ANSI sequence mangling if used in multi-threading
    lock = threading.Lock()

    #: Internal: tracks last used background attribute to avoid mangling and enable optimizations
    last_background = None
    #: Internal: tracks last used foreground attribute to avoid mangling and enable optimizations
    last_color = None
    #: Internal: tracks last used effects attribute to avoid mangling and enable optimizations
    last_effects = None

    def __init__(self, size=(), clear_screen=True, backend="ansi"):
        if not size:
            #: Set in runtime to a method to retrieve the screen width, height.
            #: The class is **not** aware of terminal resizings while running, though.
            self.get_size = lambda: V2(os.get_terminal_size())
            try:
                size = self.get_size()
            except OSError as error:
                if error.errno == 25:
                    logger.error(
                        "This terminal type does not allow guessing screen size."
                        "Pass an explicit (cols, rows) size when instantiating {self.__class__}"
                    )
                raise
        else:
            self.get_size = lambda: V2(size)

        #: Namespace to configure drawing and printing color and other parameters.
        #: Currently, the attributes that are used from here are
        #: ``color``, ``background``, ``direction``, ``effects`` and ``char``.
        self.context = Context()

        #: Namespace for drawing methods, containing an instance of the :any:`Drawing` class
        self.draw = Drawing(self.set_at, self.reset_at, self.get_size, self.context)
        self.width, self.height = self.size = size

        #: Namespace to allow high-resolution drawing using a :any:`HighRes` instance
        #: One should either use the public methods in HighRes or the methods on the
        #: :any:`Drawing` instance at ``Screen.high.draw`` to do 1/4 block pixel
        #: manipulation.
        self.high = HighRes(self)
        self.braille = HighRes(
            self, block_class=BrailleChars, block_width=2, block_height=4
        )
        self.square = HighRes(
            self, block_class=HalfChars, block_width=1, block_height=2
        )

        self.text = terminedia.text.Text(self)

        self.backend = backend = backend.upper()
        if backend == "ANSI":
            from terminedia.terminal import JournalingScreenCommands as CommandsClass
        elif backend == "HTML":
            from terminedia.html import JournalingHTMLCommands as CommandsClass
        else:
            raise ValueError(f"Unrecognized backend: {backend!r}.")

        #: Namespace for low-level rendering commands, an instance of :any:`JournalingCommandsMixin`.
        #: This attribute can be used as a context manager to group
        #: various output operations in a single block that is rendered at once.
        self.commands = CommandsClass()
        self.clear_screen = clear_screen
        self.data = FullShape.new((self.width, self.height))
        # Synchronize context for data and screen painting.
        self.data.context = self.context
        from terminedia import context
        self.root_context = context
        self._last_setitem = 0

    @LazyBindProperty(type=Context)
    def context(self):
        return Context()

    def __enter__(self):
        """Enters a fresh screen context"""
        if self.clear_screen:
            self.commands.toggle_buffer()
        self.clear(self.clear_screen)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Leaves the screen context and reset terminal colors."""
        if self.clear_screen:
            if self.commands.alternate_terminal_buffer:
                self.commands.toggle_buffer()
            else:
                #self.commands.clear()
                #self.commands.moveto((0, 0))
                pass
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
        self.context.last_pos = V2(0, 0)
        self.__class__.last_color = None
        self.__class__.last_background = None
        with self.lock:
            if wet_run:
                self.commands.clear()
                self.data.clear()
            else:
                self.data.clear(transparent=True)
            self.data.dirty_set()
            self.commands.cursor_hide()

    def set_at(self, pos, pixel=None):
        """Sets pixel at given coordinate

        Args:
          - pos (2-sequence): pixel coordinate
          - pixel (Optional[Pixel]): sets the context values according to pixel attributes prior to printing

        To be used as a callback to ``.draw.set`` - but there are no drawbacks
        in being called directly.
        """
        if pixel:
            self[pos] = pixel
        else:
            self[pos] = self.context.char

    def reset_at(self, pos):
        """Resets pixel at given coordinate

        Args:
          - pos (2-sequence): pixel coordinate

        To be used as a callback to ``.draw.reset`` - but there are no drawbacks
        in being called directly.
        """

        self[pos] = EMPTY
        pos = V2(pos)
        if self[pos + (1, 0)] == CONTINUATION:
            self[pos + (1, 0)] = EMPTY

    def line_at(self, pos, length, sequence=FULL_BLOCK):
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
        pos = V2(pos)
        if not sequence:
            return
        direction = V2(self.context.direction)
        for i, char in zip(range(length), sequence * (ceil(length / len(sequence)))):
            self[pos.as_int] = char
            pos += direction

    @contextkwords(text_attrs=True)
    def print_at(self, pos, text):
        """Positions the cursor and prints a text sequence

        Args:
          - pos (2-sequence): screen coordinates, (0, 0) being the top-left corner.
          - text: Text to render at position

        Context's attributes are respected when printing
        """
        self.text[1].at(pos, text)

    @contextkwords
    def print(self, text, **kwargs):
        """Prints a text sequence following the last character printed

        Args:
          - text: Text to render at position

        Context's attributes are respected when printing
        """
        """Prints text picking at the last position that were printed to."""
        self.text[1].print(text)

    def __getitem__(self, pos):
        """Retrieves character data at pos

        Args:
          - pos (2-sequence): coordinate to retrieve data from.
        """
        return self.data[pos].value
        # if value[0] == CONTEXT_COLORS: value[0] = self.context.color
        # if value[1] == CONTEXT_COLORS: value[1] = self.context.background
        ## FIXME: 'CONTEXT_COLORS' may clash with a effects flag combination in the future.
        # if value[2] == CONTEXT_COLORS: value[2] = self.context.effects

    def __setitem__(self, pos, value):
        """Writes character data at pos

        Args:
          - pos (2-sequence): coordinate where to set character
          - value (length 1 string): Character to set.

        This is mostly used internally by all other drawing and printing methods, although
        it can be used directly, by using Python's object-key notation with ``[ ]`` and assignment.
        All text or graphics that go to the terminal *are directed through this method*
        - it is a "single point" where all data is sent - and any user code that writes to
        the terminal with a Screen class should use this method.
        Valus set on Screen are imediately updated on the screen. To issue a command
        batch that should be updated at once, use the Screen.commands attribute as
        a context manager:  (`with sc.commands: ...code with lots of drawing calls ... `)

        If it is desired to  draw/write in an in-memory buffer in order
        to update everything at once, one can issue the drawing class to affect
        the Screen.data attribute instead of Screen directly. The Screen contents
        can be updated by calling Screen.update afterwards.  `Screen.data` is a
        terminedia.FullShape object with a .draw, .high and .text interfaces
        offering the same APIs available to Screen.

        """

        cls = self.__class__
        with self.lock:
            # Force underlying shape machinnery to apply context attributes and transformations:
            if value != _REPLAY:
                self.data[pos] = value
            pixel = self.data[pos]

            update_colors = (
                cls.last_color != pixel.foreground
                or cls.last_background != pixel.background
                or cls.last_effects != pixel.effects
            )

            if self.root_context.interactive_mode and time.time() - self._last_setitem > 0.1:
                update_colors = True
                self.commands.__class__.last_pos = None
                self._last_setitem = time.time()

            if update_colors:
                colors = pixel.foreground, pixel.background, pixel.effects
                self.commands.set_colors(*colors)
                cls.last_color = pixel.foreground
                cls.last_background = pixel.background
                cls.last_effects = pixel.effects
            if pixel.value not in (CONTINUATION, TRANSPARENT):
                self.commands.print_at(pos, pixel.value)
                self.context.last_pos = V2(pos)

    def blit(self, position, shape, **kwargs):
        with self.commands:
            self.draw.blit(position, shape, **kwargs)

    def update(self, pos1=None, pos2=None):

        rect = Rect(pos1, pos2)
        if rect.c2 == (0, 0) and pos2 is None:
            rect.c2 = (self.width, self.height)
        if hasattr(self.commands, "fast_render") and self.root_context.fast_render:
            target = [rect] if pos1 is not None or self.root_context.interactive_mode else self.data.dirty_rects
            self.commands.fast_render(self.data, target)
            self.data.dirty_clear()
        else:
            with self.commands:
                for y in range(rect.top, rect.bottom):
                    for x in range(rect.left, rect.right):
                        self[x, y] = _REPLAY
        tick_forward()
        if self.root_context.interactive_mode:
            # move cursor a couple lines from the bottom to avoid scrolling
            for i in range(3):
                self.commands.up()

    def __repr__(self):
        return "".join(
            [
                "Screen [\n",
                f"size = {self.get_size()}\n",
                f"backend = {self.backend.__class__}",
                f"context = {self.context.__repr__() if self.context else ''}\n",
                "]",
            ]
        )
