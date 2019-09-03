import time
import sys
from functools import lru_cache

from terminedia.constants import DEFAULT_BG, DEFAULT_FG


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
          - \\*args: strings to be joined by "sep" and printed
          - sep: Separator to join \\*args
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
          - \\*args: Sequence of parameters to the command, including the last
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
          - \\*args: Sequence of parameters to the SGR command,

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
