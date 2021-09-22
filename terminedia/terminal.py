import re
import time
import sys

import fcntl
import os

from functools import lru_cache
from io import StringIO
from threading import Lock

from terminedia.backend_common import BackendColorContextMixin, JournalingCommandsMixin
from terminedia.contexts import active_context
from terminedia.unicode import char_width
from terminedia.unicode_transforms import translate_chars
from terminedia.utils import V2, Color, Rect
from terminedia.values import DEFAULT_BG, DEFAULT_FG, Effects, unicode_effects_set, ESC, UNICODE_EFFECTS, TERMINAL_EFFECTS, CONTINUATION, EMPTY, TRANSPARENT

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
    E.fraktur: {E.italic},
}


unicode_effect_cache = {}



class UnblockTTY:
    """When changing the terminal to raw mode, stdin and stdout it become "unblocking"
    meaning that a large amount of output might raise an IO Error
    (BlockingIOError) when refreshing the output.

    Any code using realtime keyboard reading (using "with terminedia.keyboard:", or
    the main_loop) make this change to raw mode. (code for that is on the terminedia.input file)

    This allows screen refreshing code to temporarily disable
    the non-blocking nature of the files to avoid this error
    """

    def __enter__(self):
        self.fd = sys.stdin.fileno()
        # save old state
        self.flags_save = fcntl.fcntl(self.fd, fcntl.F_GETFL)
        #self.attrs_save = termios.tcgetattr(self.fd)
        flags = self.flags_save & ~os.O_NONBLOCK
        fcntl.fcntl(self.fd, fcntl.F_SETFL, flags)

    def __exit__(self, *args):
        #termios.tcsetattr(self.fd, termios.TCSAFLUSH, self.attrs_save)
        fcntl.fcntl(self.fd, fcntl.F_SETFL, self.flags_save)





class ScreenCommands(BackendColorContextMixin):
    """Low level functions to execute ANSI-Sequence-related tasks on the terminal.

    Although not private, this class is meant to be used internally by the higher level
    :any:`Screen` and :any:`Drawing` classes. One might use these functions directly if
    there is no interest in the other functionalities of the library, though,
    or, to make use of a custom ANSI sequence which is not available in the higher level
    API.
    """

    locks = {}
    last_pos = None

    def __init__(self, absolute_movement=True, force_newlines=False):
        self.alternate_terminal_buffer = 0
        self.active_unicode_effects = Effects.none
        self.__class__.last_pos = None
        self.absolute_movement = absolute_movement
        self.force_newlines = force_newlines

    def __repr__(self):
        return "".join(
            [
                "ScreenCommands [\n",
                f"active_unicode_effects = {self.active_unicode_effects}\n",
                f"last_pos = {self.__class__.last_pos}\n",
                "]",
            ]
        )

    def _print(self, *args, sep="", end="", flush=True, file=None):
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

        """
        if file is None:
            file = sys.stdout
        if sys.platform == "win32":
            print(sep.join(args), end=end, flush=flush, file=file)
            return

        with UnblockTTY():
            if len(args) != 1:
                file.write(sep.join(args))
            else:
                file.write(args[0])
            file.write(end)
            if flush:
                file.flush()
        return


        # FIXME: there was a previous code with retry attempts.
        # and breaking the data into chunks.
        # most of this code was written to avoid
        # an "blocking error" when outputing too much data
        # to a posix terminal converted to raw mode.
        # The temporary change of the terminal back to blocking
        # should have fixed it.
        # TL;DR: cludge removed


    def fast_render(self, data, rects=None, file=None):
        key = getattr(file, "name", "<stdout>")
        if key not in self.__class__.locks:
            self.__class__.locks[key] = Lock()
        with self.__class__.locks[key]:
            return self._fast_render(data, rects, file)

    def _fast_render(self, data, rects=None, file=None):
        if file is None:
            file = sys.stdout
        if rects is None:
            rects = {Rect((0,0), data.size)}
        CSI = "\x1b["
        SGR = "m"
        MOVE = "H"
        last_pos = self.__class__.last_pos
        last_fg = last_bg = last_tm_effects = last_un_effects = None
        seen = set()
        for rect in sorted(rects):
            if not isinstance(rect, Rect):
                rect = Rect(rect)
            outstr = ""
            for y in range(rect.top, rect.bottom):
                for x in range(rect.left, rect.right):
                    if (x, y) in seen: continue
                    seen.add((x, y))
                    # Fast render just for full-4tuple values.
                    char, fg, bg, effects = data[x, y]
                    if effects != TRANSPARENT:
                        tm_effects = effects & TERMINAL_EFFECTS
                        un_effects = effects & UNICODE_EFFECTS
                    else:
                        tm_effects = un_effects = Effects.none

                    csi = False

                    if fg != last_fg and fg != TRANSPARENT:
                        outstr += CSI
                        csi = True
                        if fg == DEFAULT_FG:
                            outstr += "39"
                        else:
                            outstr += "38;2;{};{};{}".format(*fg)

                    if bg != last_bg and bg != TRANSPARENT:
                        if not csi:
                            outstr += CSI
                            csi = True
                        else:
                            outstr += ";"
                        if bg == DEFAULT_BG:
                            outstr += "49"
                        else:
                            outstr += "48;2;{};{};{}".format(*bg)

                    if tm_effects != last_tm_effects and effects != TRANSPARENT:
                        semic = ";"
                        if not csi:
                            outstr += CSI
                            semic = ""
                            csi = True

                        if last_tm_effects:
                            for effect in last_tm_effects:
                                if effect not in tm_effects:
                                    outstr += f"{semic}{effect_off_map[effect]}"
                                    semic = ";"
                        for effect in tm_effects:
                            outstr += f"{semic}{effect_on_map[effect]}"
                            semic = ";"

                    if csi:
                        outstr += "m"
                        last_fg = fg; last_bg = bg; last_tm_effects = tm_effects
                    if char is CONTINUATION:
                        # ensure two spaces for terminedia double-width chars -
                        # can possibly be made more efficient if run in a terminal
                        # that treat those correctly (not the case in current era konsole)
                        outstr += EMPTY
                    if char not in (TRANSPARENT, CONTINUATION):
                        if (x, y) != last_pos:
                            # TODO: relative movement?
                            outstr += CSI + f"{y + 1};{x + 1}H"
                        final_char = self.apply_unicode_effects(char, un_effects)
                        outstr += final_char

                        last_pos = (x + 1, y)

            if file is sys.stdout:
                # temporarily disable 'non-blocking' for stdout
                with UnblockTTY():
                    file.write(outstr)
                    file.flush()
            else:
                file.write(outstr)
                file.flush()

            self.__class__.last_pos = last_pos



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
        args = ";".join(str(arg) for arg in args[:-1]) if args else ""
        self._print("\x1b[", args, command, file=file)

    def SGR(self, *args, file=None):
        """Writes a SGR command (Select Graphic Rendition)

        Args:
          - \\*args: Sequence of parameters to the SGR command,

        This function calls .CSI with the command fixed as "m"
          which is "SGR".
        """
        self.CSI(*args, "m", file=file)

    def clear(self, file=None):
        """Writes ANSI Sequence to clear the screen"""
        self.CSI(2, "J", file=file)

    def cursor_hide(self, file=None):
        """Writes ANSI Sequence to hide the text cursor"""
        self.CSI("?25", "l", file=file)

    def cursor_show(self, file=None):
        """Writes ANSI Sequence to show the text cursor"""
        self.CSI("?25", "h", file=file)

    def toggle_buffer(self, file=None):
        self.CSI("?1049", "l" if self.alternate_terminal_buffer else "h", file=file)
        self.alternate_terminal_buffer = not self.alternate_terminal_buffer

    def up(self, amount=1, file=None):
        """Writes ANSI Sequence to move cursor up"""
        self.CSI(amount, "A", file=file)

    def down(self, amount=1, file=None):
        """Writes ANSI Sequence to move cursor down"""
        self.CSI(amount, "B", file=file)

    def right(self, amount=1, file=None):
        """Writes ANSI Sequence to move cursor right"""
        self.CSI(amount, "C", file=file)

    def left(self, amount=1, file=None):
        """Writes ANSI Sequence to move cursor left"""
        self.CSI(amount, "D", file=file)

    def apply_unicode_effects(self, txt, effects=None):
        effects = effects if effects is not None else self.active_unicode_effects

        if (effects, txt) in unicode_effect_cache:
            return unicode_effect_cache[effects, txt]

        result = translate_chars(txt, effects)
        unicode_effect_cache[effects, txt] = result
        return result

    def home(self, file=None):

        self.CSI(f"0;0H", file=file)
        self.__class__.last_pos = V2(0,0)


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
        if self.absolute_movement:
            self.CSI(f"{pos.y + 1};{pos.x + 1}H", file=file)
        else:
            if self.__class__.last_pos and pos.y == self.__class__.last_pos.y + 1:
                self._print("\n", file=file)
                if pos.x != 0:
                    self.right(pos.x, file=file)
            else:
                if not self.__class__.last_pos:
                    self.__class__.last_pos = V2(0,0)
                delta_x = pos.x - self.__class__.last_pos.x
                delta_y = pos.y - self.__class__.last_pos.y
                if delta_y > 0:
                    if self.force_newlines:
                        self._print("\n" * delta_y, file=file)
                        delta_x = pos.x
                    else:
                        self.down(delta_y, file=file)
                elif delta_y < 0:
                    self.up(-delta_y, file=file)

                if delta_x > 0:
                    self.right(delta_x, file=file)
                elif delta_x < 0:
                    self.left(-delta_x, file=file)


        self.__class__.last_pos = pos


    def save_cursor_position(self, file=None):
        """Saves the current cursor position (in the TTY software)"""
        self.CSI("s", file=file)

    SCP = save_cursor_position

    def restore_cursor_position(self, file=None):
        """Restores saved cursor position (in the TTY software)"""
        self.CSI("u", file=file)

    RCP = restore_cursor_position

    def print(self, *texts, pos=None, context=None, color=None, background=None, effects=None,
              file=None, flush=False, sep=" ", end="\n"
              ):
        """Method to print a straightforward rich-text string to the terminal

        Params:
          *texts: List[str]: strings to print
          pos: Optional[Tuple[int, int]]: Terminal position to print to
          context: Optional[terminedia.Context instance]
          color: Union[terminedia.Color, str, Tuple[int, int, int], Tuple[float, float, float]] : foreground color to use
          background: Union[terminedia.Color, str, Tuple[int, int, int], Tuple[float, float, float]] : background color to use
          effects: terminedia.Effects : effect or effect combination to apply to characters before printing
          file, flush, sep, end: The same as standard Python's `print`

        """

        if not context:
            context = active_context.get()

        color = color or context.color
        background = background or context.background
        effects = effects or context.effects

        self.set_colors(color, background, effects, file=file)

        if self.active_unicode_effects:
            texts = [self.apply_unicode_effects(text) if text[0] != ESC else text for text in texts]

        if pos:
            self.__class__.last_pos = None
            self.moveto(pos, file=file)

        self._print(*texts, file=file, flush=flush, sep=sep, end=end)

    def print_at(self, pos, text, file=None):
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
        if text[0] != ESC and self.active_unicode_effects:
            text = self.apply_unicode_effects(text)

        self.moveto(pos, file=file)
        self._print(text, file=file)

        # (double width chars are ignored on purpose - as the repositioning
        # skipping one char to the left on the higher level classes will
        # re be reissued instead of skipped)
        self.__class__.last_pos += (len(text), 0)

    def reset_colors(self, file=None):
        """Writes ANSI sequence to reset terminal colors to the default"""
        self.SGR(0, file=file)

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

    def set_effects(
        self,
        effects,
        *,
        reset=True,
        turn_off=False,
        update_active_only=False,
        file=None,
    ):
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

        if effects is TRANSPARENT:
            return

        sgr_codes = []

        effect_map = effect_off_map if turn_off else effect_on_map
        active_unicode_effects = Effects.none

        for effect_enum in Effects:
            if effect_enum is Effects.none:
                continue
            if effect_enum in unicode_effects_set:
                if effect_enum & effects:
                    active_unicode_effects |= effect_enum
                continue
            if effect_enum & effects:
                sgr_codes.append(effect_map[effect_enum])
            elif reset and (
                not effect_enum in effect_double_off
                or not any(e & effects for e in effect_double_off[effect_enum])
            ):
                sgr_codes.append(effect_off_map[effect_enum])

        self.active_unicode_effects = active_unicode_effects
        if not update_active_only:
            self.SGR(*sgr_codes, file=file)


class JournalingScreenCommands(JournalingCommandsMixin, ScreenCommands):
    """Internal use class to optimize writting ANSI-Sequence commands to the terminal
    """
    pass


def cls():
    """Clears the output terminal.

    (if using Screen prefer "Screen.clear()")
    """
    cmd = ScreenCommands()
    cmd.clear()
    cmd.moveto((0,0))
