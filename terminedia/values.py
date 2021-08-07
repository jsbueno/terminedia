from copy import copy
from enum import Enum, IntFlag, EnumMeta

from terminedia.utils import mirror_dict, V2, NamedV2, Color, SpecialColor, IterableFlag
from terminedia.utils.collections import RetrieveFromNameEnumMeta, OrableByNameEnumMixin

ESC = "\x1b"

def _lazy_app_context():
    from terminedia import context

    return context


class SpecialColors(Enum):
    DEFAULT_FG = SpecialColor(
        "DEFAULT_FG",
        component_source=lambda color: _lazy_app_context().default_fg.components,
    )
    DEFAULT_BG = SpecialColor(
        "DEFAULT_BG",
        component_source=lambda color: _lazy_app_context().default_bg.components,
    )
    CONTEXT_COLORS = SpecialColor("CONTEXT_COLORS")
    TRANSPARENT = SpecialColor("TRANSPARENT")


#: Constant used as color to mean the default terminal foreground
#: (Currently all other color values should be RGB)
DEFAULT_FG = SpecialColors.DEFAULT_FG.value
#: Constant used as color to mean the default terminal background
DEFAULT_BG = SpecialColors.DEFAULT_BG.value
#: Constant used as color to mean keep the current context colors
CONTEXT_COLORS = SpecialColors.CONTEXT_COLORS.value
#: Constant to mean keep the current value on setting a pixel, used as char, fg, bg or effect
TRANSPARENT = SpecialColors.TRANSPARENT.value

#: Special value to mean no transformation to a given channel
#: on context-transforms. (See `terminedia.utils.create_transformer`)
NOP = "NOP"
#: Special value used in character data maps to indicate
#: the cell continues a double width character to the left
CONTINUATION = "CONT"

#: Character to denote an empty-space on images and drawing contexts
EMPTY = "\x20"
#: Character to denote a filled-pixel on images and drawing contexts
FULL_BLOCK = "\u2588"


class IterableNS(type):
    def __iter__(cls):
        return (v for k, v in cls.__dict__.items() if k[0] != "_")


class Directions(metaclass=IterableNS):
    """Direction vector constants.

    These are used directly as text-printing direction on
    a :any:`Screen` context, and are free for general use
    in user applications
    """

    UP = NamedV2(0, -1)
    RIGHT = NamedV2(1, 0)
    DOWN = NamedV2(0, 1)
    LEFT = NamedV2(-1, 0)

    def __iter__(self):
        return iter((self.UP, self.RIGHT, self.DOWN, self.LEFT))


class Effects(OrableByNameEnumMixin, IterableFlag, metaclass=RetrieveFromNameEnumMeta):
    """Text effect Enums

    Some of these are implemented in most terminal programs -
    the codes used here are so that their value can be ORed.
    (The "real" codes for terminal rendering are issued
    in ``terminal.py``).

    The somewhat arbitrary order tries to put first
    the most supported/most useful attributes.
    """
    none = 0
    bold = 1
    italic = 2
    underline = 4
    reverse = 8
    blink = 16
    faint = 32
    fast_blink = 64
    conceal = 128
    crossed_out = 256
    double_underline = 512
    framed = 1024
    encircled = 2048
    overlined = 4096
    fraktur = 8192
    squared = 16384
    negative_squared = 32768
    negative_circled = 65536
    parenthesized = 2 ** 17
    fullwidth = 2 ** 18
    math_bold = 2 ** 19
    math_bold_italic = 2 ** 20
    super_bold = 2 ** 21
    super_script = 2 ** 22
    upside_down = 2 ** 23
    double_struck = 2 ** 24


# Effects that are rendered by character translation / unicode combining
# rather than by ANSI terminal sequences
unicode_effects_set = {
    Effects.encircled,
    Effects.squared,
    Effects.negative_squared,
    Effects.negative_circled,
    Effects.parenthesized,
    Effects.fullwidth,
    Effects.math_bold,
    Effects.math_bold_italic,
    Effects.super_bold,
    Effects.super_script,
    Effects.upside_down,
    Effects.double_struck,
}

UNICODE_EFFECTS = Effects(
    sum(effect for effect in Effects if effect in unicode_effects_set)
)

TERMINAL_EFFECTS =  Effects((max(Effects) * 2 -1) - UNICODE_EFFECTS)

# (encircled is actually defined as an ANSI effect, but no terminal
# support for it was found at codification time.)


class _TextStyleSentinels(Enum):
    RETAIN_POS = "RETAIN_POS"

    def __repr__(self):
        return self.value


RETAIN_POS = _TextStyleSentinels.RETAIN_POS


class RelativeMarkIndex:
    '''
    These are used for creating Marks on terminedia.text.Text objects that
    are relative to the width and height of the object.
    Needed for Marks that should automatically be moved when the padding area
    of those planes is reassigned
    '''
    def __init__(self, name):
        self.name = name
        self.offset = 0

    def evaluate(self, size):
        # NB: this can't be named "value" because the attribute name "value"
        # is treated specially when adding a component to a V2 class
        # (V2, in turn, does that to fetch values from Enums)
        if self.name == "WIDTH":
            return size[0] + self.offset
        elif self.name == "HEIGHT":
            return size[1] + self.offset

    def __add__(self, other):
        instance = self
        if other: # not in(0, None):
            instance = copy(self)
            instance.offset += other
        return instance

    def __sub__(self, other):
        instance = self
        if other:
            instance = copy(self)
            instance.offset -= other
        return instance

    def __rsub__(self, other):
        instance = copy(self)
        instance.offset = - instance.offset
        instance.offset += other
        return instance

    def __radd__(self, other):
        return self.__add__(other)

    def __hash__(self):
        return hash((self.name, self.offset))

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return self.name == other.name and self.offset == other.offset

    @classmethod
    def evaluate_position(cls, pos, old_pos, size):
        return V2(
            pos[0].evaluate(size) if isinstance(pos[0], cls) else pos[0] if not pos[0] is RETAIN_POS else old_pos[0],
            pos[1].evaluate(size) if isinstance(pos[1], cls) else pos[1] if not pos[1] is RETAIN_POS else old_pos[1]
        )

    def __repr__(self):
        return self.name if self.offset == 0 else f"<{{{self.name} {self.offset:+d}}}>"


WIDTH_INDEX = RelativeMarkIndex("WIDTH")
HEIGHT_INDEX = RelativeMarkIndex("HEIGHT")
