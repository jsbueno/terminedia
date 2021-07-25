import binascii
from copy import copy
from pathlib import Path

from terminedia.image import Shape, PalettedShape
from terminedia.utils import contextkwords, V2, Rect
from terminedia.values import Directions, EMPTY, TRANSPARENT

try:
    # This is the only Py 3.7+ specific thing in the project
    from importlib import resources
except ImportError:
    resources = None


font_registry = {}


def _normalize_font_path(font_path):
    font_is_resource = font_path == "" or not Path(font_path).exists()
    if font_is_resource:
        if font_path == "16":
            font_path = "unscii-16-full.hex"
        elif "unscii-8" not in font_path:
            if font_path in ("", "fantasy", "mcr", "thin"):
                font_path = f"unscii-8{'-' if font_path else ''}{font_path}.hex"
    return font_path, font_is_resource


def list_fonts():
    """List font-files available with installed terminedia.

        Compliant fonts can be used and rendered if their
        full-file-path is supplied in target.context.font
        (current implementation uses human-readable, one glyph per line,
        hex font files as made available by the UNSCII project).

        Fonts can be used by their aliases: default unscii-8-font is used
        if font is the empty string  "". unscii-16, if the name includes
        "16", and unscii 8 variants need only their distinct infix
        like "fantasy", "mcr" or "thin".
    """
    if not resources:
        path = Path(__file__).parent.parent / "data"
        files = [str(f) for f in path.iterdir()]
    else:
        files = list(resources.contents("terminedia.data"))
    return [f for f in files if f.endswith(".hex")]


def load_font(font_path, font_is_resource, page=0, ch1=EMPTY, ch2="#"):

    initial = page << 8
    last = initial + 0x100

    if font_is_resource and resources:
        data = list(resources.open_text("terminedia.data", font_path))

    elif font_is_resource and not resources:
        path = Path(__file__).parent / "data" / font_path
        data = list(open(path).readlines())
    else:
        # TODO: enable more font types, and
        # TODO: enable fallback to other fonts if glyphs not present in the requested one
        data = list(open(font_path).readlines())

    font = {}

    for i, line in enumerate(data[initial:last], initial):
        line = line.split(":")[1].strip()
        line = binascii.unhexlify(line)
        char = "\n".join(f"{bin(v).split('b')[1]}".zfill(8) for v in line)
        char = char.replace("0", ch1).replace("1", ch2)
        font[chr(i)] = char

    return font


GLYPH_CACHE = {}


def render(text, font=None, shape_cls=PalettedShape, direction=Directions.RIGHT):
    if font is None:
        font = ""
    font_id, is_resource = _normalize_font_path(font)

    font = font_registry.get(font_id, None)

    if not font:
        # Always load page-0 (first 256 chars)
        font_registry.setdefault(font_id, {}).update(load_font(font_id, is_resource))
        font = font_registry[font_id]

    cache_index = (font_id, shape_cls, text)
    if len(text) == 1 and cache_index in GLYPH_CACHE:
        return GLYPH_CACHE[cache_index]

    phrase = []
    for char in text:
        if char not in font:
            font.update(load_font(font_id, is_resource, page=ord(char)//0x100))
        phrase.append(shape_cls(font.get(char, "?")))

    if len(text) == 0:
        return shape_cls.new((0, 0))
    elif len(text) == 1:
        GLYPH_CACHE[cache_index] = phrase[0]
        return phrase[0]
    return phrase[0].concat(*phrase[1:], direction=direction)

