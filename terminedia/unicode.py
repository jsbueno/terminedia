"""Tools to explore/fetch Unicode characters in a user friendly way
"""

import re
import unicodedata
from collections import namedtuple
from copy import copy
from functools import lru_cache


CHAR_BASE = None


class Character(str):
    __slots__ = "code char name category width".split()

    def __new__(cls, value, code, name, category, width):
        self = super().__new__(cls, value)
        self.code = code
        self.name = name
        self.category = category
        self.width = width

        return self

    def __repr__(self):
            return f"Character(code=0x{self.code:04X}, value='{self}', name='{self.name}', category='{self.category}', width='{self.width}')"


def _init_chars():
    global CHAR_BASE
    if CHAR_BASE:
        return
    CHAR_BASE = {}
    for code in range(0, 0x10ffff):
        char = chr(code)
        values = {}
        attrs = "name category east_asian_width".split()
        for attr in attrs:
            try:
                values[attr] = getattr(unicodedata, attr)(char)
            except ValueError:
                values[attr] = "undefined"
        CHAR_BASE[code] = Character(char, code, values["name"], values["category"], values["east_asian_width"])


def lookup(name_part, chars_only=False):
    _init_chars()
    results = [char for char in CHAR_BASE.values() if re.search(name_part, char.name, re.IGNORECASE)]
    if not chars_only:
        return results
    return [char.char for char in results]


CGJ = "\u034f" # character used to _separate_ graphemes that would otherwise be joined - combining grapheme joiner (CGJ) U+034F


_sentinel = object()


class GraphemeIter:
    """Separates a string in a list of strings, each containing a single grapheme:
    the contiguous set of a character and combining characters to be applied to it.
    """

    def __init__(self, text):
        self.text = text

    def text_setter(self, value):
        if "text" in self.__dict__:
            raise TypeError(f"{self.__class__.__name__} is imutable")
        self.__dict__["text"] = value

    text = property(lambda s: s.__dict__["text"], text_setter)
    del text_setter

    @lru_cache()
    def __len__(self):
        return sum(1 for _ in self)

    def __iter__(self):
        category = unicodedata.category

        last_char = ""
        self._current_grapheme = -1

        for i, char in enumerate(self.text):
            self._current_char = i
            if not category(char)[0] == 'M' and last_char:
                self._current_grapheme += 1
                yield last_char
                last_char = ""
            last_char += char
        if last_char:
            self._current_grapheme += 1
            yield last_char

    def iter_cooked_indexes(self, indexes):
        """Translate indexes on the underlying raw string to positions in the iterator

        passed indexes must be sorted in ascending order
        """
        instance = copy(self)
        instance._current_char = -1
        x = iter(instance)
        results = []
        last_index = -1
        v = None
        for index in indexes:
            if index >= len(instance.text) or instance._current_char >= len(instance.text):
                return
            if index < last_index:
                raise ValueError("This iterable must be called with indexes in ascending order")

            if index < instance._current_char:
                yield instance._current_grapheme
                continue

            while index >= instance._current_char and v is not _sentinel:
                v = next(x, _sentinel)
            if v is not _sentinel:
                yield instance._current_grapheme
            last_index = index



split_graphemes = lambda text: list(GraphemeIter(text))


def is_single_grapheme(text):
    category = unicodedata.category
    if len(text) <= 1:
        return True
    return all(category(char)[0] == "M" for char in text[1:])


@lru_cache()
def char_width(char, grapheme=False):
    """Return a character width as being 1 or 2 -
    since terminedia is all about monospaced cells, other values
    are of no interest
    """


    #FIXME: findout a way to perform a lazy import only once -
    # the import statements are expensive, and this function
    # is called often
    from terminedia.subpixels import BlockChars, SextantChars

    if char in BlockChars.chars or char in SextantChars.chars:
        return 1
    if len(char) > 1:
        return max(char_width(combining, grapheme=True) for combining in char)
    v = unicodedata.east_asian_width(char)
    if grapheme and v == "A" and unicodedata.category(char)[0] == "M":
        return 1
    return 1 if v in ("N", "Na") else 2  # (?) include "A" as single width?
