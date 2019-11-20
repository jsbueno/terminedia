"""Terminedia is a library providing utilities to control and draw on the text terminal

Usage: import terminedia main classes and constants and control the terminal
is if it is a multi-functional canvas.
Drawing primitives that operate with block chars are provided, as well as
non-blocking keyboard reading.
"""

import sys

if sys.platform == "win32":
    import colorama
    colorama.init(convert=True)

from terminedia.contexts import Context, RootContext
from terminedia.input import keyboard, inkey, pause, KeyCodes
from terminedia.utils import Color, Rect, V2, create_transformer
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

__version__ = "0.3.dev0"
__author__ = "João S. O. Bueno"


# These will be used for other backends than terminal rendering:
context = RootContext(default_fg="white", default_bg="black")

del RootContext
