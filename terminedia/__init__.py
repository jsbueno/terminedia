"""Terminedia is a library providing utilities to control and draw on the text terminal

Usage: import terminedia main classes and constants and control the terminal
is if it is a multi-functional canvas.
Drawing primitives that operate with block chars are provided, as well as
non-blocking keyboard reading.
"""

from terminedia.keyboard import realtime_keyb, inkey, pause, KeyCodes
from terminedia.utils import Rect, V2, create_transformer
from terminedia.terminal import ScreenCommands, JournalingScreenCommands
from terminedia.values import Directions, Effects, DEFAULT_BG, DEFAULT_FG, CONTEXT_COLORS, TRANSPARENT, NOP
from terminedia.image import shape, ValueShape, ImageShape, PalettedShape, FullShape
from terminedia.screen import Screen, Context
from terminedia.subpixels import BlockChars
from terminedia.text import render

__version__ = "0.3.dev0"
__author__ = "João S. O. Bueno"


