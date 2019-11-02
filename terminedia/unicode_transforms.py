"""unicode_transforms creates text effects based on UNICODE character
transformations. Those effects depends on the fonts available in the system"""
import re
import unicodedata
from functools import lru_cache

from terminedia.values import Effects
from terminedia.utils import FrozenDict as FD


LATIN_DIGIT_REG = r"(?P<family>LATIN)?\s?(?P<case>(CAPITAL|SMALL|DIGIT))?\s?(?P<type>LETTER)?\s?(?P<symbol>.+)"

# TODO: use a template and automate the setting of helping text to the 'text_to' functions
# Or refactor all 'text_to" functions to a dictionary)

_template = """
    Convert ASCII letters and digits in a string to unicode "{effect_name}" character variants

      Args:
        - text(str): Text to convert.
        - Convert(bool): whether to try to convert non-compliant characters to ones with representation.

    Used internally to apply the "{effect_name}" effect as a character
    translation, this replaces unicode chars by their decorated
    encircled counterparts.
    It is used as a part of the rendering machinery, but
    it is a plain function that can be called directly just
    for the translation.
    """


@lru_cache()
def _name_based_translation(
    text,
    convert,
    substitution,
    match=r"[A-Z]",
    convert_lower=True,
    convert_upper=False,
    fallback_dict=None,
):
    """Internal generic code to transform characters using unicode-name strategy
    """
    if not r"\g<" in substitution:
        # If no regexp group substituion in the string, treat it as a prefix.
        substitution += r" \g<0>"
    fallback_dict = fallback_dict or {}
    result = ""
    combining = ""
    for char in text:
        new_char = char
        if convert:
            new_char = unicodedata.normalize("NFKD", new_char)
            new_char, combining = new_char if len(new_char) == 2 else (new_char, "")

        if re.match(match, new_char):
            if convert_lower and re.match(r"[a-z]", new_char):
                new_char = new_char.upper()
            if convert_upper and re.match(r"[A-Z]", new_char):
                new_char = new_char.lower()
            name = re.sub(LATIN_DIGIT_REG, substitution, unicodedata.name(new_char))
            try:
                char = combining + f"\\N{{{name}}}".encode().decode("UNICODE_ESCAPE")
            except UnicodeDecodeError:
                char = fallback_dict.get(char, char)
        result += char

    return result


def text_to_circled(text, convert=True):
    return _name_based_translation(
        text, convert, "CIRCLED", r"[A-Za-z0-9]", convert_lower=False
    )


def text_to_negative_circled(text, convert=True):
    return _name_based_translation(
        text, convert, "NEGATIVE CIRCLED", r"[A-Za-z0]", convert_lower=True
    )


def text_to_squared(text, convert=True):
    return _name_based_translation(
        text, convert, "SQUARED", r"[A-Za-z0]", convert_lower=True
    )


def text_to_negative_squared(text, convert=True):
    return _name_based_translation(
        text, convert, "NEGATIVE SQUARED", r"[A-Za-z0]", convert_lower=True
    )


def text_to_parenthesized(text, convert=True):
    return _name_based_translation(
        text, convert, "PARENTHESIZED", r"[A-Za-z0-9]", convert_lower=False
    )


def text_to_fullwidth(text, convert=True):
    return _name_based_translation(
        text,
        convert,
        "FULLWIDTH",
        r"[A-Za-z0-9!@#$%*()-+=[\]{}/|]",
        convert_lower=False,
    )


def text_to_san_serif_bold(text, convert=True):
    # example name: ('MATHEMATICAL SANS-SERIF BOLD CAPITAL A',)
    return _name_based_translation(
        text,
        convert,
        r"MATHEMATICAL SANS-SERIF BOLD \g<case> \g<symbol>",
        match=r"[a-zA-Z0-9]",
        convert_lower=False,
    )


def text_to_san_serif_bold_italic(text, convert=True):
    # example name: ('MATHEMATICAL SANS-SERIF BOLD ITALIC CAPITAL A',)
    return _name_based_translation(
        text,
        convert,
        r"MATHEMATICAL SANS-SERIF BOLD ITALIC \g<case> \g<symbol>",
        match=r"[a-zA-Z]",
        convert_lower=False,
    )


def text_to_regional_indicator_symbol(text, convert=True):
    # REGIONAL INDICATOR SYMBOL LETTER A',
    return _name_based_translation(
        text,
        convert,
        r"REGIONAL INDICATOR SYMBOL LETTER \g<symbol>",
        match=r"[a-zA-Z]",
        convert_lower=True,
    )


def text_to_modifier_letter(text, convert=True):
    # MODIFIER LETTER SMALL A
    # TODO: More than half capital letters and a lot of symbols
    # are available in this variant. Going with lower case only.
    return _name_based_translation(
        text,
        convert,
        r"MODIFIER LETTER SMALL \g<symbol>",
        match=r"[a-zA-Z]",
        convert_lower=False,
        convert_upper=True,
        fallback_dict=FD({"i": "\N{MODIFIER LETTER CAPITAL I}"}),
    )


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
        Effects.negative_squared: text_to_negative_squared,
        Effects.negative_circled: text_to_negative_circled,
        Effects.parenthesized: text_to_parenthesized,
        Effects.fullwidth: text_to_fullwidth,
        Effects.math_bold: text_to_san_serif_bold,
        Effects.math_bold_italic: text_to_san_serif_bold_italic,
        Effects.super_bold: text_to_regional_indicator_symbol,
        Effects.super_script: text_to_modifier_letter,
    }
    for effect in unicode_effects:
        text = effect_dict.get(effect, _nop_effect)(text, convert)
    return text
