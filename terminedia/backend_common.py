import re
import time
import sys
from functools import lru_cache
from io import StringIO

from terminedia.unicode import char_width
from terminedia.unicode_transforms import translate_chars
from terminedia.utils import V2, Color
from terminedia.values import DEFAULT_BG, DEFAULT_FG, Effects, UNICODE_EFFECTS, ESC


class BackendColorContextMixin:

    def reset_colors(self, file=None):
        """Writes ANSI sequence to reset terminal colors to the default"""
        self.current_foreground = None
        self.current_background = None

    def set_colors(self, foreground, background, effects=Effects.none, file=None):
        """Sets internal states foreground and background colors and character effects to apply
        foreground: the foreground color
        background: the background color
        effects: Character effects t obe applied.
        """
        self.set_fg_color(foreground, file=file)
        self.set_bg_color(background, file=file)
        self.set_effects(effects, file=file)

    def set_fg_color(self, color, file=None):
        """
        """
        self.next_foreground = Color(color)

    def set_bg_color(self, color, file=None):
        """
        """
        self.next_background = Color(color)

    def set_effects(self, effects, *, update_active_only=False, file=None):
        """Sets internal state so that next characters rendered have character effects applied

        update_active_only parameter is meant for low-level interactive
        use of the terminal, and make no sense when rendering to HTML, but is kept
        for signature compatibility
        """
        # effect_map = effect_off_map if turn_off else effect_on_map
        active_unicode_effects = Effects.none
        for effect in effects:
            if effect in UNICODE_EFFECTS:
                active_unicode_effects |= effect

        self.active_unicode_effects = active_unicode_effects
        self.next_effects = effects


    def apply_unicode_effects(self, txt):
        return translate_chars(txt, self.active_unicode_effects)



class JournalingCommandsMixin(BackendColorContextMixin):
    """Internal use class to write ANSI-Sequence commands to the terminal

    This class implements a journaling technique to group commands to be
    sent to the output. It should be combined with a class implementing
    concrete output to a backend type - like ANSI Sequences TXT or
    HTML Backend.

    While it exposes the same methods than the backend class,
    the "print_at", "set_foreground" and "set_background" methods can be used
    in a managed context to group all commands so that all writtings to
    the output will be made in as few calls to write to the output stream
    as possible.

    Although user code directly calling the methods in this class is not
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

    def __init__(self, **kwargs):
        """__init__ initializes internal attributes"""
        self.in_block = 0
        self.current_color = DEFAULT_FG
        self.current_background = DEFAULT_BG
        self.current_effect = Effects.none
        self.current_pos = 0, 0
        super().__init__(**kwargs)

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
            (
                self.tick,
                char,
                self.current_color,
                self.current_background,
                self.current_effect,
            )
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

    def stop_journal(self):
        """Manually stops journalling so that recorded contents can be replayed"""
        self.in_block = 0

    def replay(self, file=None, single_write=True):
        """Renders the commands recorded to the terminal screen.
          Args:
            - file (Optional[TextIO]): Optional file to render command-content to.
            - single_write (Bool): Whether to incrementally call print for every character
            or to do a single call to print once the content is set-up.
            Backend dependendant parameter.

        This collects the last-writting in each screen position,
        groups same-color in consecutive left-to-right characters to avoid
        redundant color-setting sequences.

        It is called automatically on exiting a managed-context -
        but can be called manually to render partially whatever commands
        are recorded so far. The journal is not touched and
        can be further used inside the same context.

        If optional `file` is passed, all contents are written  in as a
        text sequence in an optmized top-left to bottom-right stream with the appropriate backend commands
        to position each character (and set colors, etc...).
        (note it should be a text-file, if any of the characters to be rendered
        is not valid in the file inner encoding, it will rase an UnicodeEncode error).

        """
        last_color = last_bg = None
        last_effect = Effects.none
        last_pos = None
        # buffer = ""
        original_file = file
        file = StringIO() if not original_file else original_file

        if single_write:
            writer = file.write
        else:
            writer = lambda char: self._print(char, file=file)

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
                for func, arg in call:
                    func(arg, file=file)

            writer(char)

            width = (char_width(char), 0)
            last_pos += width
            self.__class__.last_pos = last_pos

        if not original_file and single_write:
            self._print(file.getvalue())

    def print_at(self, pos, txt, file=None):
        """Positions the cursor and prints a text sequence

        Args:
          - pos (2-sequence): screen coordinates, (0, 0) being the top-left corner.
          - txt: Text to render at position
          - file: Alternative file file to be used in final output, rather than sys.stdout

        All characters are logged into the journal if inside a managed block.
        """

        if not self.in_block:
            return super().print_at(pos, txt, file=file)

        # pre-transform characters, we bypass super().print_at
        if txt[0] != ESC and self.active_unicode_effects:
            txt = self.apply_unicode_effects(txt)

        for x, char in enumerate(txt, pos[0]):
            self._set(V2(x, pos[1]), char)

    def set_fg_color(self, color, file=None):
        """Writes ANSI sequence to set the foreground color

        Args:
          - color (constant or 3-sequence): RGB color (0.0-1.0 or 0-255 range) or constant to set as fg color
        """
        if not self.in_block:
            super().set_fg_color(color, file=file)
        self.current_color = color

    def set_bg_color(self, color, file=None):
        """Writes ANSI sequence to set the background color

        Args:
          - color (constant or 3-sequence): RGB color (0.0-1.0 or 0-255 range) or constant to set as fg color
        """
        if not self.in_block:
            super().set_bg_color(color, file=file)
        self.current_background = color

    def set_effects(self, effects, file=None):
        super().set_effects(effects, update_active_only=self.in_block, file=file)
        self.current_effect = effects
