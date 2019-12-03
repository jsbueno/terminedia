"""Tools to explore/fetch Unicode characters in a user friendly way
"""

import re
import unicodedata

from collections import namedtuple
from functools import lru_cache


Character = namedtuple("Character", "code char name category width")

CHAR_BASE = None

def _init_chars():
    global CHAR_BASE
    if CHAR_BASE:
        return
    CHAR_BASE = {}
    for i in range(0, 0x10ffff):
        char = chr(i)
        attrs = "name category east_asian_width"
        values = {}
        for attr in attrs.split():
            try:
                values[attr] = getattr(unicodedata, attr)(char)
            except ValueError:
                values[attr] = "undefined"
        CHAR_BASE[i] = Character(i, char, values["name"], values["category"], values["east_asian_width"])


def lookup(name_part, chars_only=False):
    _init_chars()
    results = [char for char in CHAR_BASE.values() if re.search(name_part, char.name, re.IGNORECASE)]
    if not chars_only:
        return results
    return [char.char for char in results]

