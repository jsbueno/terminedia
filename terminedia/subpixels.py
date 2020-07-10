import unicodedata

from terminedia import values
from terminedia.utils import mirror_dict


class SubPixels:
    """Used internally to emulate pixel setting/resetting/reading inside unicode block characters

    Requires that the subclasses contain a listing and other mappings
    of all block characters to be used in order, so that
    bits in numbers from 0 to `bit_size` will match the "pixels" on the corresponding block character.

    Although this class is purposed for internal use in the emulation of
    a higher resolution canvas, its functions can be used by any application
    that decides to manipulate block chars.

    The class itself is stateless, and any subclass can be used as a single-instance.
    The instance is needed so that one can use the operator
    ``in`` to check if a character is a block-character in that resolution.

    (originally this code was in the BlockChars class - and was refactored
    to include the other sub-block pixel resolutions. This class is used as base,
    and depends mostly of declaring the pixel-representing characters in order
    in the subclass.)

    """
    # TODO: with proper profiling some better performance to set/unset subpixels
    # can be achieved (like, declaring the lambda-operators out of the methods
    # to skip building the function object on each call)

    block_width: int
    block_height: int
    bit_size: int = 0b1111

    def __init_subclass__(cls):
        # This depends on Python 3.6+ ordered behavior for local namespaces and dicts:
        cls.chars_by_name = chars_by_name = {
            key: value for key, value in cls.__dict__.items() if key.isupper()
        }
        cls.chars_to_name = mirror_dict(chars_by_name)
        cls.chars_in_order = {
            i: value for i, value in enumerate(chars_by_name.values())
        }
        cls.chars_to_order = mirror_dict(cls.chars_in_order)
        cls.chars = set(chars_by_name.values())

    def __contains__(self, char):
        """True if a char is a "pixel representing" unicode character"""
        return char in self.chars

    @classmethod
    def _op(cls, pos, data, operation):
        number = cls.chars_to_order[data]
        index = 2 ** (pos[0] + cls.block_width * pos[1])
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
        return cls.chars_in_order[cls._op(pos, data, op)]

    @classmethod
    def reset(cls, pos, data):
        """"resets" a pixel in a block character

        Args:
          - pos (2-sequence): coordinate of the pixel inside the character
            (0,0) is top-left corner, and so on)
          - data: initial character to be composed with the bit to be reset.
        """
        op = lambda n, index: n & (cls.bit_size - index)
        return cls.chars_in_order[cls._op(pos, data, op)]

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


class BlockChars_(SubPixels):
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

    block_width = 2
    block_height = 2

    EMPTY = values.EMPTY
    QUADRANT_UPPER_LEFT = "\u2598"
    QUADRANT_UPPER_RIGHT = "\u259D"
    UPPER_HALF_BLOCK = "\u2580"
    QUADRANT_LOWER_LEFT = "\u2596"
    LEFT_HALF_BLOCK = "\u258C"
    QUADRANT_UPPER_RIGHT_AND_LOWER_LEFT = "\u259E"
    QUADRANT_UPPER_LEFT_AND_UPPER_RIGHT_AND_LOWER_LEFT = "\u259B"
    QUADRANT_LOWER_RIGHT = "\u2597"
    QUADRANT_UPPER_LEFT_AND_LOWER_RIGHT = "\u259A"
    RIGHT_HALF_BLOCK = "\u2590"
    QUADRANT_UPPER_LEFT_AND_UPPER_RIGHT_AND_LOWER_RIGHT = "\u259C"
    LOWER_HALF_BLOCK = "\u2584"
    QUADRANT_UPPER_LEFT_AND_LOWER_LEFT_AND_LOWER_RIGHT = "\u2599"
    QUADRANT_UPPER_RIGHT_AND_LOWER_LEFT_AND_LOWER_RIGHT = "\u259F"
    FULL_BLOCK = values.FULL_BLOCK


#: :any:`BlockChars_` single instance: enables ``__contains__``:
BlockChars = BlockChars_()


class HalfChars_(SubPixels):
    """Used internally to emulate pixel setting/resetting/reading inside 1/2 Character Blocks"""

    block_width = 1
    block_height = 2
    bit_size: int = 0b11

    EMPTY = values.EMPTY
    UPPER_HALF_BLOCK = "\u2580"
    LOWER_HALF_BLOCK = "\u2584"

    FULL_BLOCK = values.FULL_BLOCK

    @classmethod
    def _op(cls, pos, data, operation):
        number = cls.chars_to_order[data]
        index = 1 + pos[1]
        return operation(number, index)

HalfChars = HalfChars_()


class BrailleChars_(SubPixels):
    """Used internally to emulate pixel setting/resetting/reading inside 1/8 Unicode Braille characters"""

    block_width = 2
    block_height = 4
    bit_size: int = 0b11111111

    EMPTY = values.EMPTY

    for codepoint in range(0x2801, 0x2900):
        char = chr(codepoint)
        locals()[unicodedata.name(char)] = char
    del codepoint, char

    @classmethod
    def _op(cls, pos, data, operation):
        number = cls.chars_to_order[data]
        index = (2 ** (pos[1] + 3 * pos[0])) if pos[1] < 3 else (2 ** (6 + pos[0]))
        return operation(number, index)


BrailleChars = BrailleChars_()

if int(unicodedata.unidata_version.split(".")[0]) >= 13:
    sextant_name_picker = unicodedata.name
else:
    def sextant_name_picker(char):
        n = ord(char) - 0x1fb00
        return f"SEXTANT CHAR {n:02d} PROVISIONAL)"

class SextantChars_(SubPixels):
    """Used internally to emulate pixel setting/resetting/reading inside 1/6 Unicode Legacy Computing characters"""

    block_width = 2
    block_height = 3
    bit_size: int = 0b111111

    EMPTY = values.EMPTY

    for codepoint in range(0x1FB00, 0x1FB3C):
        char = chr(codepoint)
        locals()[sextant_name_picker(char)] = char
        # This Unicode plane do not re-implement these 2 chars,
        # so we insert then manually in the correct order
        if codepoint == 0x1fb13:
            LEFT_HALF_BLOCK = "\u258C"
        if codepoint == 0x1fb27:
            RIGHT_HALF_BLOCK = "\u2590"
    FULL_BLOCK = values.FULL_BLOCK

    del codepoint, char


SextantChars = SextantChars_()















# draft chars to look at later:
# Future chars to acomodate in extended drawing modes:
"""
U+25E2	◢	e2 97 a2	BLACK LOWER RIGHT TRIANGLE
U+25E3	◣	e2 97 a3	BLACK LOWER LEFT TRIANGLE
U+25E4	◤	e2 97 a4	BLACK UPPER LEFT TRIANGLE
U+25E5	◥	e2 97 a5	BLACK UPPER RIGHT TRIANGLE
"""

a = "  ◢◣◤◥"
a = "◢◣◤◥"
