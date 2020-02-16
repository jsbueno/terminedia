"""Tools to explore/fetch Unicode characters in a user friendly way
"""

import re
import unicodedata

from collections import namedtuple
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
        attrs = "name category east_asian_width"
        for attr in attrs.split():
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

