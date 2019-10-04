from enum import Enum, IntFlag

from terminedia.utils import mirror_dict, V2, NamedV2


#: Constant used as color to mean the default terminal foreground
#: (Currently all other color values should be RGB)
DEFAULT_FG = 0xffff
#: Constant used as color to mean the default terminal background
DEFAULT_BG = 0xfffe
#: Constant used as color to mean keep the current context colors
CONTEXT_COLORS = 0xfffd
#: Constant to mean keep the current value, usd as char, fg, bg or effect
TRANSPARENT = 0xfffc
#: Special value to mean no transformation to a given channel
#: on context-transforms. (See `terminedia.utils.create_transformer`)
NOP = "NOP"
#: Special value used in character data maps to indicate
#: the cell continues a double width character to the left
CONTINUATION = "CONT"

class Directions:
    """Direction vector constants.

    These are used directly as text-printing direction on
    a :any:`Screen` context, and are free to general use
    in user applications
    """
    UP = NamedV2(0, -1)
    RIGHT = NamedV2(1, 0)
    DOWN = NamedV2(0, 1)
    LEFT = NamedV2(-1, 0)


class Effects(IntFlag):
    """Text effect Enums

    Some of these are implemented in most terminal programs -
    the codes used here are so that their value can be ORed.
    (The "real" codes for terminal rendering are issed
    in ``terminal.py``).

    The somewhat arbitrary order tries to put first
    the most supported/most useful attributes.
    """
    def __iter__(self):
        """much hacky. very smart: composed flags are now iterable!"""
        for element in self.__class__:
            if self & element:
                yield element

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


# Effects that are rendered by character translation / unicode combining
# rather than by ANSI terminal sequences
unicode_effects = {
    Effects.encircled, Effects.squared, Effects.negative_squared,
    Effects.negative_circled, Effects.parenthesized, Effects.fullwidth
}
UNICODE_EFFECTS = Effects(sum(effect for effect in Effects if effect in unicode_effects))

# (encircled is actually defined as an ANSI effect, but no terminal
# support for it was found at encoding time.)


ESC = "\x1b"

# braille base code = 10240.

class BlockChars_:
    """Used internally to emulate pixel setting/resetting/reading inside 1/4 block characters

    Contains a listing and other mappings of all block characters used in order, so that
    bits in numbers from 0 to 15 will match the "pixels" on the corresponding block character.

    Although this class is purposed for internal use in the emulation of
    a higher resolution canvas, its functions can be used by any application
    that decides to manipulate block chars.

    The class itself is stateless, and it is used as a single-instance which
    uses the name :any:`BlockChars`. The instance is needed so that one can use the operator
    ``in`` to check if a character is a block-character.

    """
    EMPTY = " "
    QUADRANT_UPPER_LEFT = '\u2598'
    QUADRANT_UPPER_RIGHT = '\u259D'
    UPPER_HALF_BLOCK = '\u2580'
    QUADRANT_LOWER_LEFT = '\u2596'
    LEFT_HALF_BLOCK = '\u258C'
    QUADRANT_UPPER_RIGHT_AND_LOWER_LEFT = '\u259E'
    QUADRANT_UPPER_LEFT_AND_UPPER_RIGHT_AND_LOWER_LEFT = '\u259B'
    QUADRANT_LOWER_RIGHT = '\u2597'
    QUADRANT_UPPER_LEFT_AND_LOWER_RIGHT = '\u259A'
    RIGHT_HALF_BLOCK = '\u2590'
    QUADRANT_UPPER_LEFT_AND_UPPER_RIGHT_AND_LOWER_RIGHT = '\u259C'
    LOWER_HALF_BLOCK = '\u2584'
    QUADRANT_UPPER_LEFT_AND_LOWER_LEFT_AND_LOWER_RIGHT = '\u2599'
    QUADRANT_UPPER_RIGHT_AND_LOWER_LEFT_AND_LOWER_RIGHT = '\u259F'
    FULL_BLOCK = '\u2588'

    # This depends on Python 3.6+ ordered behavior for local namespaces and dicts:
    block_chars_by_name = {key: value for key, value in locals().items() if key.isupper()}
    block_chars_to_name = mirror_dict(block_chars_by_name)
    blocks_in_order = {i: value for i, value in enumerate(block_chars_by_name.values())}
    block_to_order = mirror_dict(blocks_in_order)

    def __contains__(self, char):
        """True if a char is a "pixel representing" block char"""
        return char in self.block_chars_to_name

    @classmethod
    def _op(cls, pos, data, operation):
        number = cls.block_to_order[data]
        index = 2 ** (pos[0] + 2 * pos[1])
        return operation(number, index)

    @classmethod
    def set(cls, pos, data):
        """"Sets" a pixel in a block character

        Args:
          - pos (2-sequence): coordinate of the pixel inside the character
            (0,0) is top-left corner, (1,1) bottom-right corner and so on)
          - data: initial character to be composed with the bit to be set. Use
            space ("\x20") to start with an empty block.

        """
        op = lambda n, index: n | index
        return cls.blocks_in_order[cls._op(pos, data, op)]

    @classmethod
    def reset(cls, pos, data):
        """"resets" a pixel in a block character

        Args:
          - pos (2-sequence): coordinate of the pixel inside the character
            (0,0) is top-left corner, (1,1) bottom-right corner and so on)
          - data: initial character to be composed with the bit to be reset.
        """
        op = lambda n, index: n & (0xf - index)
        return cls.blocks_in_order[cls._op(pos, data, op)]

    @classmethod
    def get_at(cls, pos, data):
        """Retrieves whether a pixel in a block character is set

        Args:
          - pos (2-sequence): The pixel coordinate
          - data (character): The character were to look at blocks.

        Raises KeyError if an invalid character is passed in "data".
        """
        op = lambda n, index: bool(n & index)
        return cls._op(pos, data, op)


#: :any:`BlockChars_` single instance: enables ``__contains__``:
BlockChars = BlockChars_()

# Future chars to acomodate in extended drawing modes:
"""
U+25E2	◢	e2 97 a2	BLACK LOWER RIGHT TRIANGLE
U+25E3	◣	e2 97 a3	BLACK LOWER LEFT TRIANGLE
U+25E4	◤	e2 97 a4	BLACK UPPER LEFT TRIANGLE
U+25E5	◥	e2 97 a5	BLACK UPPER RIGHT TRIANGLE
"""

a = "  ◢◣◤◥"
a = "◢◣◤◥"
