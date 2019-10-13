import re
import time
import sys
from functools import lru_cache
from io import StringIO

from terminedia.unicode_transforms import translate_chars
from terminedia.utils import char_width, V2, Color
from terminedia.values import DEFAULT_BG, DEFAULT_FG, Effects, unicode_effects, ESC

full_body_template = """\
<!DOCTYPE html>
<head>
  <meta charset="utf-8">
</head>
<body>
  <div style="font-family: monospace; width:{width}em; height: {height}em; background: {background}; position: relative">
     {content}
  </div>
</body>
</html>
"""

open_tag = """<span style="{style}">"""
close_tag = """</span>\n"""

# Space normalizer
D = lambda str: " ".join(str.split())



class HTMLCommands:
    """
    """

    last_pos = None

    def __init__(self):
        self.active_unicode_effects = set()
        self.last_pos = None
        self.next_pos = V2(0,0)

        self.current_foreground = None
        self.current_background = None
        self.current_effect = None
        self.next_foreground = Color((0,0,0))
        self.next_background = Color((255, 255, 255))
        self.next_effect = Effects.none

        self.tag_is_open = False

    @property
    def dirty_state(self):
        return self.current_foreground != self.next_foreground or \
            self.current_background != self.next_background or \
            self.current_effect != self.next_effect

    def actualize_state(self):
        self.current_foreground = self.next_foreground
        self.current_background = self.next_background
        self.current_effect = self.next_effect

    def print(self, *args, sep='', end='', flush=True, file=None, count=0):
        """Write needed HTML tags with inline style to positin and color given text"""
        if file is None:
            file = sys.stdout
        if end == "\n":
            break_line = True
            end = ""
        else:
            break_line = False
        content = sep.join(args) + end
        if self.next_pos == self.last_pos and self.tag_is_open and self.dirty_state:
            file.write(sep.join(args) + end)
            self.last_pos += len(content)
        else:
            if self.tag_is_open:
                file.write(close_tag)
            self.actualize_state()
            tag_attrs = D(f"""\
                position: absolute;
                left: {self.next_pos.x};
                top: {self.next_pos.y};
                color: {self.current_foreground.html;}
                background: {self.current_background.html;}
            """)
            # TODO some terminal effects map directly to
            # CSS styles, such as underline, overline, bold and blink
            # these should be coded above;
            tag = open_tag.format(style=tag_attrs)
            file.write(tag + content)
            self.tag_is_open = True
        if flush or break_line:
            file.write(close_tag)
            self.tag_is_open = False
        if break_line:
            file.write("<br>\n")
            self.next_pos = V2(0, self.last_pos.y + 1)
        else:
            self.next_pos = self.last_pos
        if self.flush:
            file.flush()


    def moveto(self, pos, file=None):
        """Set internal state so that next character rendering is at the new coordinates;

        Args:
          - pos (2-sequence): screen coordinates, (0, 0) being the top-left corner.

        """
        self.next_pos = V2(pos)

    def apply_unicode_effects(self, txt):
        return translate_chars(txt, self.active_unicode_effects)

    def print_at(self, pos, txt, file=None):
        """Positions the cursor and prints a text sequence

        Args:
          - pos (2-sequence): screen coordinates, (0, 0) being the top-left corner.
          - txt: Text to render at position

        """
        if self.active_unicode_effects:
            txt = self.apply_unicode_effects(txt)

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
        self.next_color = Color(color)


    def set_bg_color(self, color, file=None):
        """
        """
        self.next_background = Color(color)


    def set_effects(self, effects, *, reset=True, turn_off=False, update_active_only=False, file=None):
        """Sets internal state so that next characters rendered have character effects applied

        """
        self.next_effects = effects

