import re
import time
import sys
from functools import lru_cache
from io import StringIO

from terminedia.backend_common import JournalingCommandsMixin
from terminedia.unicode_transforms import translate_chars
from terminedia.utils import char_width, V2, Color
from terminedia.values import DEFAULT_BG, DEFAULT_FG, Effects, unicode_effects, ESC

use_re_split = sys.version_info >= (3, 7)

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
        self.active_unicode_effects = Effects.none
        self.__class__.last_pos = None

    def __repr__(self):
        return "".join(["ScreenCommands [\n",
                        f"active_unicode_effects = {self.active_unicode_effects}\n",
                        f"last_pos = {self.__class__.last_pos}\n",
                        "]",
                        ])

    def print(self, *args, sep='', end='', flush=True, file=None, count=0):
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
        if file is None:
            file = sys.stdout
        try:
            if len(args) == 1 and "\x1b" in args[0] and file is sys.stdout:
                # Separate a long sequence in one write operation for each
                # ANSI command
                sep = end = ''
                if use_re_split:
                    # This is new in Python 3.7
                    args = re.split("(?=\x1b)", args[0])
                else:
                    args = [("\x1b" if i else "") + arg for i, arg in enumerate(args[0].split("\x1b"))]
            for arg in args:
                file.write(arg)
                if sep:
                    file.write(sep)
            if end:
                file.write(end)
            if flush:
                file.flush()
        except BlockingIOError:
            if count > 10:
                print("arrrrghhhh - stdout clogged out!!!", file=sys.stderr)
                raise
            time.sleep(0.002 * 2 ** count)
            self.print(*args, sep=sep, end=end, flush=flush, file=file, count=count + 1)

    def CSI(self, *args, file=None):
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
        self.print("\x1b[", args, command, file=file)

    def SGR(self, *args, file=None):
        """Writes a SGR command (Select Graphic Rendition)

        Args:
          - \\*args: Sequence of parameters to the SGR command,

        This function calls .CSI with the command fixed as "m"
          which is "SGR".
        """
        self.CSI(*args, 'm', file=file)

    def clear(self, file=None):
        """Writes ANSI Sequence to clear the screen"""
        self.CSI(2, 'J', file=file)

    def cursor_hide(self, file=None):
        """Writes ANSI Sequence to hide the text cursor"""
        self.CSI('?25', 'l', file=file)

    def cursor_show(self, file=None):
        """Writes ANSI Sequence to show the text cursor"""
        self.CSI('?25', 'h', file=file)

    def moveto(self, pos, file=None):
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
        self.CSI(f'{pos.y + 1};{pos.x + 1}H', file=file)
        self.__class__.last_pos = V2(pos)

    def print_at(self, pos, txt, file=None):
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

        self.moveto(pos, file=file)
        self.print(txt, file=file)

        # (double width chars are ignored on purpose - as the repositioning
        # skipping one char to the left on the higher level classes will
        # re be reissued instead of skipped)
        self.__class__.last_pos += (len(txt), 0)

    def reset_colors(self, file=None):
        """Writes ANSI sequence to reset terminal colors to the default"""
        self.SGR(0, file=file)

    def set_colors(self, foreground, background, effects=Effects.none, file=None):
        """Sets foreground and background colors on the terminal
        foreground: the foreground color
        background: the background color
        """
        self.set_fg_color(foreground, file=file)
        self.set_bg_color(background, file=file)
        self.set_effects(effects, file=file)

    def set_fg_color(self, color, file=None):
        """Writes ANSI sequence to set the foreground color
        color: RGB  3-sequence (0.0-1.0 or 0-255 range) or color constant
        """
        if color == DEFAULT_FG:
            self.SGR(39, file=file)
        else:
            self.SGR(38, 2, *Color(color), file=file)

    def set_bg_color(self, color, file=None):
        """Writes ANSI sequence to set the background color
        color: RGB  3-sequence (0.0-1.0 or 0-255 range) or color constant
        """
        if color == DEFAULT_BG:
            self.SGR(49, file=file)
        else:
            self.SGR(48, 2, *Color(color), file=file)

    def set_effects(self, effects, *, reset=True, turn_off=False, update_active_only=False, file=None):
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
        active_unicode_effects = Effects.none

        for effect_enum in Effects:
            if effect_enum is Effects.none:
                continue
            if effect_enum in unicode_effects:
                if effect_enum & effects:
                    active_unicode_effects |= effect_enum
                continue
            if effect_enum & effects:
                sgr_codes.append(effect_map[effect_enum])
            elif reset and (not effect_enum in effect_double_off or
                            not any(e & effects for e in effect_double_off[effect_enum])):
                sgr_codes.append(effect_off_map[effect_enum])

        self.active_unicode_effects = active_unicode_effects
        if not update_active_only:
            self.SGR(*sgr_codes, file=file)


class JournalingScreenCommands(JournalingCommandsMixin, ScreenCommands):
    """Internal use class to optimize writting ANSI-Sequence commands to the terminal
    """
    pass
