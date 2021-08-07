"""unicode_transforms creates text effects based on UNICODE character
transformations. Those effects depends on the fonts available in the system"""
import re
import unicodedata
from functools import lru_cache

from terminedia.values import Effects
from terminedia.utils import FrozenDict as FD, mirror_dict


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

# The higher level classes of terminedia always call these on a char-by-char
# basis - but one could use these directly to convert text blocks of arbitrary
# content - the cap on the LRU cache is to prevent deterioration with this use.

# @lru_cache(1024)
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


@lru_cache(1024)
def _dict_based_translation(text, mapping, convert=True):
    if convert:
        text = unicodedata.normalize("NFKD", text)
    return "".join(mapping.get(char, char) for char in text)


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


def text_to_double_struck(text, convert=True): # WIP
    return _name_based_translation(
        text, convert, r"MATHEMATICAL DOUBLE-STRUCK \g<case> \g<symbol>",
        r"[A-Za-z0-9]", convert_lower=False,
        fallback_dict=FD({
            "C": "\N{DOUBLE-STRUCK CAPITAL C}",
            "H": "\N{DOUBLE-STRUCK CAPITAL H}",
            "P": "\N{DOUBLE-STRUCK CAPITAL P}",
            "Q": "\N{DOUBLE-STRUCK CAPITAL Q}",
            "R": "\N{DOUBLE-STRUCK CAPITAL R}",
            "Z": "\N{DOUBLE-STRUCK CAPITAL Z}",
            }),
    )


def text_to_upside_down(text, convert=True):
    """Use a table of custom characters to find aproximate upside-down glyphs"""
    return _dict_based_translation(text, UPSIDE_DOWN_MAPPING, convert)

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
        Effects.upside_down: text_to_upside_down,
        Effects.double_struck: text_to_double_struck,
    }
    for effect in unicode_effects:
        text = effect_dict.get(effect, _nop_effect)(text, convert)
    return text



# Based on the translation map at
# https://www.fileformat.info/convert/text/upside-down-map.htm (2019-12-15)
# which in turn is based in the work by David Faden at http://www.revfad.com/flip.html
# which in turn thanks the names "Brook Monroe, Tim McCormack, Glards,
# and Yeeliberto amongst others for further suggestions." (user names at reddit)

# Also, some chars were complemented by research into the charset,
# and from the https://github.com/cburgmer/upsidedown by Christoph Burgmer

_upside_down_build = {
    '\u0021' : '\u00A1',
    '\u0022' : '\u201E',
    '\u0026' : '\u214B',
    '\u0027' : '\u002C',
    '\u0028' : '\u0029',
    '\u002E' : '\u02D9',
    '\u0031' : '\N{LATIN CAPITAL LETTER IOTA}',
    '\u0033' : '\u0190',
    '\u0034' : '\u152D',
    '\u0036' : '\u0039',
    '\u0037' : '\u2C62',
    '\u003B' : '\u061B',
    '\u003C' : '\u003E',
    '\u003F' : '\u00BF',
    '\u0041' : '\u2200',
    '\u0042' : '\N{DESERET CAPITAL LETTER BEE}',
    '\u0043' : '\u2183',
    '\u0044' : '\N{CANADIAN SYLLABICS CARRIER THA}',
    '\u0045' : '\u018E',
    '\u0046' : '\u2132',
    '\u0047' : '\u2141',
    '\u004A' : '\N{CANADIAN SYLLABICS CI}',
    '\u004B' : '\N{LATIN CAPITAL LETTER TURNED K}',
    '\u004C' : '\u2142',
    '\u004D' : '\u0057',
    '\u004E' : '\u1D0E',
    '\u0050' : '\u0500',
    '\u0051' : '\u038C',
    '\u0052' : '\u1D1A',
    '\u0054' : '\u22A5',
    '\u0055' : '\u2229',
    '\u0056' : '\N{LATIN CAPITAL LETTER TURNED V}',
    '\u0059' : '\u2144',
    '\u005B' : '\u005D',
    '\u005F' : '\u203E',
    '\u0061' : '\u0250',
    '\u0062' : '\u0071',
    '\u0063' : '\u0254',
    '\u0064' : '\u0070',
    '\u0065' : '\u01DD',
    '\u0066' : '\u025F',
    '\u0067' : '\u0183',
    '\u0068' : '\u0265',
    '\u0069' : '\N{LATIN SMALL LETTER TURNED I}',
    '\u006A' : '\u027E',
    '\u006B' : '\u029E',
    '\u006C' : '\N{LATIN SMALL LETTER TURNED L}',
    '\u006D' : '\u026F',
    '\u006E' : '\u0075',
    '\u0072' : '\u0279',
    '\u0074' : '\u0287',
    '\u0076' : '\u028C',
    '\u0077' : '\u028D',
    '\u0079' : '\u028E',
    '\u007B' : '\u007D',
    '\u203F' : '\u2040',
    '\u2045' : '\u2046',
    '\u2234' : '\u2235'
}

_upside_down_build.update(mirror_dict(_upside_down_build))


# _upside_down_diacritics picked from Christoph Burgmer's upside down:

_upside_down_diacritics = {
    '\N{COMBINING DIAERESIS}': '\N{COMBINING DIAERESIS BELOW}',
    '\N{COMBINING RING ABOVE}': '\N{COMBINING RING BELOW}',
    '\N{COMBINING ACUTE ACCENT}': '\N{COMBINING ACUTE ACCENT BELOW}',
    '\N{COMBINING GRAVE ACCENT}': '\N{COMBINING GRAVE ACCENT BELOW}',
    '\N{COMBINING DOT ABOVE}': '\N{COMBINING DOT BELOW}',
    '\N{COMBINING TILDE}': '\N{COMBINING TILDE BELOW}',
    '\N{COMBINING MACRON}': '\N{COMBINING MACRON BELOW}',
    '\N{COMBINING CIRCUMFLEX ACCENT}': '\N{COMBINING CARON BELOW}',
    '\N{COMBINING BREVE}': '\N{COMBINING INVERTED BREVE BELOW}',
    '\N{COMBINING CARON}': '\N{COMBINING CIRCUMFLEX ACCENT BELOW}',
    '\N{COMBINING INVERTED BREVE}': '\N{COMBINING BREVE BELOW}',
    '\N{COMBINING VERTICAL LINE ABOVE}': '\N{COMBINING VERTICAL LINE BELOW}',
}

_upside_down_diacritics.update(mirror_dict(_upside_down_diacritics))
_upside_down_build.update(_upside_down_diacritics)

UPSIDE_DOWN_MAPPING = FD(_upside_down_build)

del _upside_down_build, _upside_down_diacritics
