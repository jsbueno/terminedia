import re
import unicodedata

from terminedia.values import Effects


LATIN_DIGIT_REG = r"(?P<family>LATIN)?\s?(?P<case>(CAPITAL|SMALL))?\s?(?P<type>(LETTER|DIGIT))?\s?(?P<symbol>.+)"

def _name_based_translation(text, convert, substitution, convert_lower=True, match=r"[A-Z]"):
    """Internal generic code to transform characters using unicode-name strategy
    """
    if not r"\g<" in substitution:
        # If no regexp group substituion in the string, treat it as a prefix.
        substitution += r" \g<0>"
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
            name = re.sub(LATIN_DIGIT_REG, substitution, unicodedata.name(new_char))
            char = combining + f"\\N{{{name}}}".encode().decode("UNICODE_ESCAPE")
        result += char

    return result


def text_to_circled(text, convert=True):
    """Convert ASCII letters and digits in a string to unicode "circled" character variants

      Args:
        - text(str): Text to convert.
        - Convert(bool): whether to convert non-compliant characters to ones with representation.

    Used internally to apply the "circled" effect as a character
    translation, this replaces unicode chars by their decorated
    encircled counterparts.
    It is used as a part of the rendering machinery, but
    it is a plain function that can be called directly just
    for the translation.
    """
    return _name_based_translation(text, convert, "CIRCLED", False, r"[A-Za-z0-9]")


def text_to_negative_circled(text, convert=True):
    """Convert ASCII letters and digits in a string to unicode "negative circled" character variants

      Args:
        - text(str): Text to convert.
        - Convert(bool): whether to convert non-compliant characters to ones with representation.

    Used internally to apply the "negative circled" effect as a character
    translation, this replaces unicode chars by their decorated
    encircled counterparts.
    It is used as a part of the rendering machinery, but
    it is a plain function that can be called directly just
    for the translation.
    """
    return _name_based_translation(text, convert, "NEGATIVE CIRCLED", True, r"[A-Z0]")


def text_to_squared(text, convert=True):
    """Convert ASCII letters and digits in a string to unicode "squared" character variants

      Args:
        - text(str): Text to convert.
        - Convert(bool): whether to convert non-compliant characters to ones with representation.

    Used internally to apply the "squared" effect as a character
    translation, this replaces unicode chars by their decorated
    encircled counterparts.
    It is used as a part of the rendering machinery, but
    it is a plain function that can be called directly just
    for the translation.
    """
    return _name_based_translation(text, convert, "SQUARED")


def text_to_negative_squared(text, convert=True):
    """Convert ASCII letters and digits in a string to unicode "negative squared" character variants

      Args:
        - text(str): Text to convert.
        - Convert(bool): whether to convert non-compliant characters to ones with representation.

    Used internally to apply the "negative squared" effect as a character
    translation, this replaces unicode chars by their decorated
    encircled counterparts.
    It is used as a part of the rendering machinery, but
    it is a plain function that can be called directly just
    for the translation.
    """
    return _name_based_translation(text, convert, "NEGATIVE SQUARED")


def text_to_parenthesized(text, convert=True):
    """Convert ASCII letters and digits in a string to unicode "parenthesized" character variants

      Args:
        - text(str): Text to convert.
        - Convert(bool): whether to convert non-compliant characters to ones with representation.

    Used internally to apply the "parenthesized" effect as a character
    translation, this replaces unicode chars by their decorated
    encircled counterparts.
    It is used as a part of the rendering machinery, but
    it is a plain function that can be called directly just
    for the translation.
    """
    return _name_based_translation(text, convert, "PARENTHESIZED", False, r"[A-Za-z0-9]")


def text_to_fullwidth(text, convert=True):
    """Convert ASCII letters and digits in a string to unicode "fullwidth" character variants

      Args:
        - text(str): Text to convert.
        - Convert(bool): whether to convert non-compliant characters to ones with representation.

    Used internally to apply the "fullwidth" effect as a character
    translation, this replaces unicode chars by their decorated
    encircled counterparts.
    It is used as a part of the rendering machinery, but
    it is a plain function that can be called directly just
    for the translation.
    """
    return _name_based_translation(text, convert, "FULLWIDTH", False, r"[A-Za-z0-9!@#$%*()-+=[\]{}/|]")


def text_to_san_serif_bold_italic(text, convert=True):
    """Convert ASCII letters and digits in a string to unicode "MATHEMATICAL SANS-SERIF BOLD ITALIC" character variants

      Args:
        - text(str): Text to convert.
        - Convert(bool): whether to convert non-compliant characters to ones with representation.

    Used internally to apply the unicode effect as a character
    translation, this replaces unicode chars by their decorated
    encircled counterparts.
    It is used as a part of the rendering machinery, but
    it is a plain function that can be called directly just
    for the translation.
    """

    # example name: ('MATHEMATICAL SANS-SERIF BOLD ITALIC CAPITAL A',)
    #text = "0"
    return _name_based_translation(text, convert,
        r"MATHEMATICAL SANS-SERIF BOLD ITALIC \g<case> \g<symbol>",
        convert_lower=False,
        match=r"[a-zA-Z]"
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
        Effects.math_bold_italic: text_to_san_serif_bold_italic
    }
    for effect in unicode_effects:
        text = effect_dict.get(effect, _nop_effect)(text, convert)
    return text

