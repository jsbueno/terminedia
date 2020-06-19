import re
import time
import sys
from io import StringIO

from terminedia.backend_common import BackendColorContextMixin, JournalingCommandsMixin
from terminedia.unicode import char_width
from terminedia.unicode_transforms import translate_chars
from terminedia.utils import V2, Color
from terminedia.values import DEFAULT_BG, DEFAULT_FG, Effects, UNICODE_EFFECTS, ESC

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


class HTMLCommands(BackendColorContextMixin):
    """Backend for generating HTML monospace content with character rendition for a terminedia image.


    Used indirectlly by Shape.render when the selected render backend is HTML. It is interesting
    to note that unlike the terminal "ANSI" backend, the output stream is only touched
    by the "._print" method - the "file" parameter is ignored in other methods
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

    def _print(self, *args, sep="", end="", flush=False, file=None, count=0):
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
        self._print(txt, file=file)

    def clear(self):
        pass


class JournalingHTMLCommands(JournalingCommandsMixin, HTMLCommands):
    def replay(self, file=None, single_write=False):
        """Renders the buffered output to the given stream.

        Force the Journaling mixin to call "._print" for
        each character to be printed, since colors, position
        and other context state only takes place in the output
        stream when a character is actually printed.
        (It does not make sense to pass this as True from here)
        """
        super().replay(file=file, single_write=False)
