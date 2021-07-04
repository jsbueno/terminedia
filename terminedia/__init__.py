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

from terminedia.input import keyboard, mouse, inkey, pause, KeyCodes, getch, input as sinput
from terminedia.utils import Color, Rect, V2, Gradient, ColorGradient
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
from terminedia.subpixels import BlockChars
from terminedia.text import render
from terminedia.text.style import Mark
from terminedia.screen import Screen
from terminedia.transformers import Transformer, TransformersContainer, GradientTransformer
from terminedia.transformers.library import box_transformers as borders
# Import otherwise unused modules, so that they are
# always available after importing the main library:
import terminedia.unicode
from terminedia.events import EventTypes
from terminedia.asynchronous import terminedia_main, ainput
from terminedia.terminal import cls

import terminedia.widgets


__version__ = "0.4.dev0"
__author__ = "João S. O. Bueno"


print = ScreenCommands().print

# These will be used for other backends than terminal rendering:
context = _RootContext(default_fg="white", default_bg="black", fps=5)
context.interactive_mode = sys.argv[0] == "" or sys.argv[0].endswith("ipython")
context.fast_render = True

del _RootContext
