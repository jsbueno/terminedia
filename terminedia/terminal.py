import time
import sys
from functools import lru_cache

from terminedia.unicode_transforms import translate_chars
from terminedia.utils import char_width, V2
from terminedia.values import DEFAULT_BG, DEFAULT_FG, Effects, unicode_effects, ESC


E = Effects

#: Inner mappings with actual ANSI codes to turn on and off text effects.
#: These are defined on module escope to avoid
#: re-parsing of the dict bodies at each invocation
#: of ``set_effects``
effect_on_map = {
    E.bold: 1,
    E.italic: 3,
    E.underline: 4,
    E.reverse: 7,
    E.blink: 5,
    E.faint: 2,
    E.fast_blink: 6,
    E.conceal: 8,
    E.crossed_out: 9,
    E.double_underline: 21,
    E.framed: 51,
    E.encircled: 52,
    E.overlined: 53,
    E.fraktur: 20,
}
effect_off_map = {
    E.bold: 22,
    E.italic: 23,
    E.underline: 24,
    E.reverse: 27,
    E.blink: 25,
    E.faint: 22,
    E.fast_blink: 25,
    E.conceal: 28,
    E.crossed_out: 29,
    E.double_underline: 24,
    E.framed: 54,
    E.encircled: 54,
    E.overlined: 55,
    E.fraktur: 23,
}
#: Helper mapping to avoid automatically turning off text attributes
#: that happen to use the same code to switch off than others
effect_double_off = {
    E.bold: {E.faint},
    E.italic: {E.fraktur},
    E.underline: {E.double_underline},
    E.blink: {E.fast_blink},
    E.faint: {E.bold},
    E.fast_blink: {E.blink},
    E.double_underline: {E.underline},
    E.framed: {E.encircled},
    E.encircled: {E.framed},
    E.fraktur: {E.italic}
}

class ScreenCommands:
    """Low level functions to execute ANSI-Sequence-related tasks on the terminal.

    Although not private, this class is meant to be used internally by the higher level
    :any:`Screen` and :any:`Drawing` classes. One might use these functions directly if
    there is no interest in the other functionalities of the library, though,
    or, to make use of a custom ANSI sequence which is not available in the higher level
    API.
    """

    last_pos = None

    def __init__(self):
        self.active_unicode_effects = set()
        self.__class__.last_pos = None

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
        pos = V2(pos)
        if pos != (0, 0) and pos == self.__class__.last_pos:
            return
        # x, y = pos
        self.CSI(f'{pos.y + 1};{pos.x + 1}H')
        self.__class__.last_pos = V2(pos)

    def apply_unicode_effects(self, txt):
        return translate_chars(txt, self.active_unicode_effects)

    def print_at(self, pos, txt):
        """Positions the cursor and prints a text sequence

        Args:
          - pos (2-sequence): screen coordinates, (0, 0) being the top-left corner.
          - txt: Text to render at position

        There is an optimization that avoids re-issuing
        cursor-positioning ANSI sequences for repeated
        calls of this function - this uses a class
        attribute so that different Screen instances won't clash,
        but might yield concurrency problems if appropriate
        locks are not in place in concurrent code.
        """
        if txt[0] != ESC and self.active_unicode_effects:
            txt = self.apply_unicode_effects(txt)

        self.moveto(pos)
        self.print(txt)

        # (double width chars are ignored on purpose - as the repositioning
        # skipping one char to the left on the higher level classes will
        # re be reissued instead of skipped)
        self.__class__.last_pos += (len(txt), 0)

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

    def set_colors(self, foreground, background, effects=Effects.none):
        """Sets foreground and background colors on the terminal
        foreground: the foreground color
        background: the background color
        """
        self.set_fg_color(foreground)
        self.set_bg_color(background)
        self.set_effects(effects)

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

    def set_effects(self, effects, *, reset=True, turn_off=False, update_active_only=False):
        """Writes ANSI sequence to set text effects (bold, blink, etc...)

        When using the high-level drawing functions, each time a text-effect
        attribute is changed, all text effects are reset. The
        turn_off and reset parameters are suplied for low-level
        use of this function.

        - Args:
          effects (terminedia.Effects): enum specifying which text effects should be affected
          reset (bool): When True, all effect attributes on the screen are reset to match
                        the passed effects description. (i.e. if blinking is currently on,
                        and effects == Effect.underline, blinking will be turned off, and
                        only underline will be active). If reset is False, only the
                        underline terminal property will be affected by this call
          turn_off (bool): Only used when "reset" is False: meant to indicate
                           the specified effects should be turnned off instead of on.
          update_active_only (bool): if set, won't issue any commands to terminal, just
                            modify internal state so that effetcs that trigger character
                            translations are activated.
        """

        sgr_codes = []

        effect_map = effect_off_map if turn_off else effect_on_map


        active_unicode_effects = set()
        for effect_enum in Effects:
            if effect_enum is Effects.none:
                continue
            if effect_enum in unicode_effects:
                if effect_enum & effects:
                    active_unicode_effects.add(effect_enum)
                continue
            if effect_enum & effects:
                sgr_codes.append(effect_map[effect_enum])
            elif reset and (not effect_enum in effect_double_off or
                            not any(e & effects for e in effect_double_off[effect_enum])):
                sgr_codes.append(effect_off_map[effect_enum])

        self.active_unicode_effects = active_unicode_effects
        if not update_active_only:
            self.SGR(*sgr_codes)


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
        self.current_effect = Effects.none
        self.current_pos = 0, 0
        super().__init__()

    def __enter__(self):
        """Enters a context where screen writes are collected together.

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
          - pos (V2): coordinate where setting
          - char (strig of lenght 1): character to set

        Inside a managed context this is called to anotate the current color and position
        data to the internal Journal.
        """
        if not self.in_block:
            raise RuntimeError("Journal not open")
        self.journal.setdefault(pos, []).append(
            (self.tick, char, self.current_color, self.current_background, self.current_effect)
        )
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
        last_effect = Effects.none
        last_pos = None
        buffer = ""

        for pos in sorted(self.journal, key=lambda pos: (pos[1], pos[0])):
            tick, char, color, bg, effect = self.journal[pos][-1]
            call = []

            if pos != last_pos:
                last_pos = pos
                call.append((self.moveto, pos))

            if color != last_color:
                last_color = color
                call.append((self.set_fg_color, color))

            if bg != last_bg:
                last_bg = bg
                call.append((self.set_bg_color, bg))

            if effect != last_effect:
                last_effect = effect
                call.append((self.set_effects, effect))

            if call:
                if buffer:
                    self.print(buffer)
                    buffer = ""
                for func, arg in call:
                    func(arg)
            buffer += char
            last_pos += (1, 0)

        if buffer:
            self.print(buffer)

    def print_at(self, pos, txt):
        """Positions the cursor and prints a text sequence

        Args:
          - pos (2-sequence): screen coordinates, (0, 0) being the top-left corner.
          - txt: Text to render at position

        All characters are logged into the journal if inside a managed block.
        """

        if not self.in_block:
            return super().print_at(pos, txt)

        # pre-transform characters, we bypass super().print_at
        if txt[0] != ESC and self.active_unicode_effects:
            txt = self.apply_unicode_effects(txt)

        for x, char in enumerate(txt, pos[0]):
            self._set(V2(x, pos[1]), char)

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

    def set_effects(self, effects):
        super().set_effects(effects, update_active_only = self.in_block)
        self.current_effect = effects
