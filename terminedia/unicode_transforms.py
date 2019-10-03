import re
import unicodedata

from terminedia.values import Effects

def text_to_circled(text):
    """Convert ASCII letters and digits in a string to unicode "encircled" character variants

      Args:
        - text(str): Text to convert.

    Used internally to apply the "encircled" effect as a character
    translation, this replaces unicode chars by their decorated
    encircled counterparts.
    It is used as a part of the rendering machinery, but
    it is a plain function that can be called directly just
    for the translation.
    """
    result = ""
    for char in text:
        if re.match(r"[A-Za-z0-9]", char):
            char = f"\\N{{CIRCLED {unicodedata.name(char)}}}".encode().decode("UNICODE_ESCAPE")
        result += char
    return result


def translate_chars(text, unicode_effects):
    """Apply a sequence of character-translating effects to given text.
      Args:
        - text(str): text to be transformed
        - unicode_effects (iterable[Terminedia.Effects]): Effects to be applied


    """
    for effect in unicode_effects:
        if effect == Effects.encircled:
            text = text_to_circled(text)
    return text


def char_width(char):
    v = unicodedata.east_asian_width(char)
    return 1 if v in ("N", "Na", "A") else 2
