import re
import time
import sys
from functools import lru_cache
from io import StringIO

from terminedia.backend_common import JournalingCommandsMixin
from terminedia.unicode_transforms import translate_chars
from terminedia.utils import char_width, V2, Color
from terminedia.values import DEFAULT_BG, DEFAULT_FG, Effects, unicode_effects, ESC

full_body_template = """\
<!DOCTYPE html>
<head>
  <meta charset="utf-8">
</head>
<body>
  <div style="font-family: monospace; width:{width}em; height: {height}em; background: {background}; position: relative; white-space: pre">
     {content}
  </div>
</body>
</html>
"""


open_tag = """<span style="{style}">"""
close_tag = """</span\n>"""

# Space normalizer
D = lambda str: " ".join(str.split())


class HTMLCommands:
    """Backend for generating HTML monospace content with character rendition for a terminedia image.


    Used indirectlly by Shape.render when the selected render backend is HTML. It is interesting
    to note that unlike the terminal "ANSI" backend, the output stream is only touched
    by the ".print" method - the "file" parameter is ignored in other methods
    that just update the internal state of the instance so that the next character
    to be printed comes out correctly.
    """

    last_pos = None

    def __init__(self):
        self.active_unicode_effects = Effects.none
        self.__class__.last_pos = V2(0, 0)
        self.next_pos = V2(0, 0)

        self.current_foreground = None
        self.current_background = None
        self.current_effects = None
        self.next_foreground = Color((0, 0, 0))
        self.next_background = Color((255, 255, 255))
        self.next_effects = Effects.none

        self.tag_is_open = False

    @property
    def dirty(self):
        return (
            self.current_foreground != self.next_foreground
            or self.current_background != self.next_background
            or self.current_effects != self.next_effects
        )

    def update_state(self):
        self.current_foreground = self.next_foreground
        self.current_background = self.next_background
        self.current_effects = self.next_effects
        self.last_pos = self.next_pos

    def print(self, *args, sep="", end="", flush=False, file=None, count=0):
        """Write needed HTML tags with inline style to positin and color given text"""
        if file is None:
            file = sys.stdout
        if self.last_pos and  self.next_pos.y == self.last_pos.y + 1 and self.next_pos.x == 0:
            if self.tag_is_open:
                file.write(close_tag)
                self.tag_is_open = False
            file.write("<br/>")
        break_line = args and args[-1] == "\n"
        content = (sep.join(args) + end).strip("\n")
        if self.active_unicode_effects:
            txt = self.apply_unicode_effects(content)
        if self.next_pos == self.last_pos and self.tag_is_open and not self.dirty:
            file.write(content)
        elif not content:
            pass
        else:
            if self.tag_is_open:
                file.write(close_tag)
            self.update_state()
            color = self.current_foreground.html
            background = self.current_background.html
            if self.next_effects & Effects.faint:
                color = f"rgba{color.components + (.5,)!r}"
            if self.next_effects & Effects.reverse:
                color, background = background, color
            if self.next_effects & Effects.conceal:
                color = background
            tag_attrs = f"""\
                position: absolute;
                left: {self.next_pos.x}ch;
                top: {self.next_pos.y}em;
                color: {color};
                background: {background};
            """
            tag_attrs += (
                (
                    "text-decoration: "
                    + (
                        "underline"
                        if self.next_effects
                        & (Effects.underline | Effects.double_underline)
                        else ""
                    )
                    + ("double" if self.next_effects & Effects.double_underline else "")
                    + ("overline" if self.next_effects & Effects.overlined else "")
                    + (
                        "line-through"
                        if self.next_effects & Effects.crossed_out
                        else ""
                    )
                    + (
                        "blink"
                        if self.next_effects & (Effects.blink | Effects.fast_blink)
                        else ""
                    )
                )
                if self.next_effects
                & (
                    Effects.underline
                    | Effects.overlined
                    | Effects.crossed_out
                    | Effects.double_underline
                    | Effects.blink
                    | Effects.fast_blink
                )
                else ""
            )
            tag = open_tag.format(style=D(tag_attrs))
            file.write(tag + content)
            self.tag_is_open = True
        self.last_pos += (len(content), 0)
        if (flush or break_line) and self.tag_is_open:
            file.write(close_tag)
            self.tag_is_open = False
        if break_line:
            file.write("<br>\n")
            self.next_pos = V2(0, self.last_pos.y + 1)
        else:
            self.next_pos = (
                self.last_pos
            )  # V2(self.last_pos if self.last_pos else (0,0))
        if flush:
            file.flush()

    def moveto(self, pos, file=None):
        """Set internal state so that next character rendering is at the new coordinates;

        Args:
          - pos (2-sequence): screen coordinates, (0, 0) being the top-left corner.

        """
        self.next_pos = V2(pos)

    def print_at(self, pos, txt, file=None):
        """Positions the cursor and prints a text sequence

        Args:
          - pos (2-sequence): screen coordinates, (0, 0) being the top-left corner.
          - txt: Text to render at position

        """

        self.moveto(pos, file=file)
        self.print(txt, file=file)

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
            if effect in unicode_effects:
                active_unicode_effects |= effect

        self.active_unicode_effects = active_unicode_effects
        self.next_effects = effects

    def clear(self):
        pass


class JournalingHTMLCommands(JournalingCommandsMixin, HTMLCommands):
    def replay(self, file=None, single_write=False):
        """Renders the buffered output to the given stream.

        Force the Journaling mixin to call ".print" for
        each character to be printed, since colors, position
        and other context state only takes place in the output
        stream when a character is actually printed.
        (It does not make sense to pass this as True from here)
        """
        super().replay(file=file, single_write=False)
