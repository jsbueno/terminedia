import re
import unicodedata

from terminedia.values import Effects

def text_to_circled(text, convert=True):
    """Convert ASCII letters and digits in a string to unicode "encircled" character variants

      Args:
        - text(str): Text to convert.
        - Convert(bool): whether to convert non-compliant characters to ones with representation.

    Used internally to apply the "encircled" effect as a character
    translation, this replaces unicode chars by their decorated
    encircled counterparts.
    It is used as a part of the rendering machinery, but
    it is a plain function that can be called directly just
    for the translation.
    """
    return _name_based_translation(text, convert, "CIRCLED", False, r"[A-Za-z0-9]")


def _name_based_translation(text, convert, prefix, convert_lower=True, match=r"[A-Z]"):
    """Internal generic code to transform characters using unicode-name strategy
    """
    result = ""
    combining = ""
    for char in text:
        new_char = char
        if convert:
            new_char = unicodedata.normalize("NFKD", new_char)
            new_char, combining = new_char if len(new_char) == 2 else (new_char, "")

            if convert_lower and re.match(r"[a-z]", new_char):
                new_char = new_char.upper()
        if re.match(match, new_char):
            char = combining + f"\\N{{{prefix} {unicodedata.name(new_char)}}}".encode().decode("UNICODE_ESCAPE")
        result += char

    return result


def text_to_squared(text, convert=True):
    """Convert ASCII letters and digits in a string to unicode "squared" character variants

      Args:
        - text(str): Text to convert.
        - Convert(bool): whether to convert non-compliant characters to ones with representation.

    Used internally to apply the "encircled" effect as a character
    translation, this replaces unicode chars by their decorated
    encircled counterparts.
    It is used as a part of the rendering machinery, but
    it is a plain function that can be called directly just
    for the translation.
    """
    return _name_based_translation(text, convert, "SQUARED")


_nop_effect = lambda t, c: t


def translate_chars(text, unicode_effects, convert=True):
    """Apply a sequence of character-translating effects to given text.
      Args:
        - text(str): text to be transformed
        - unicode_effects (iterable[Terminedia.Effects]): Effects to be applied


    """
    effect_dict = {
        Effects.encircled: text_to_circled,
        Effects.squared: text_to_squared,
    }
    for effect in unicode_effects:
        text = effect_dict.get(effect, _nop_effect)(text, convert)
    return text


def char_width(char):
    v = unicodedata.east_asian_width(char)
    return 1 if v in ("N", "Na", "A") else 2
