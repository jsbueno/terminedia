"""Terminedia is a library providing utilities to control and draw on the text terminal

Usage: import terminedia main classes and constants and control the terminal
is if it is a multi-functional canvas.
Drawing primitives that operate with block chars are provided, as well as
non-blocking keyboard reading.
"""

from terminedia.contexts import Context, _RootContext
import sys

if sys.platform == "win32":
    import colorama
    colorama.init(convert=True)

from terminedia.input import keyboard, inkey, pause, KeyCodes, getch
from terminedia.utils import Color, Rect, V2, Gradient
from terminedia.sprites import Sprite
from terminedia.terminal import ScreenCommands, JournalingScreenCommands
from terminedia.values import (
    Directions,
    Effects,
    DEFAULT_BG,
    DEFAULT_FG,
    CONTEXT_COLORS,
    TRANSPARENT,
    NOP,
)
from terminedia.image import shape, ValueShape, ImageShape, PalettedShape, FullShape
from terminedia.screen import Screen
from terminedia.subpixels import BlockChars
from terminedia.text import render
from terminedia.transformers import Transformer

__version__ = "0.3.dev0"
__author__ = "João S. O. Bueno"


print = ScreenCommands().print

# These will be used for other backends than terminal rendering:
context = _RootContext(default_fg="white", default_bg="black")
context.interactive_mode = sys.argv[0] == "" or sys.argv[0].endswith("ipython")
context.fast_render = True

del _RootContext
