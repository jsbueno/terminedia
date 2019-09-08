import binascii
from pathlib import Path

from terminedia.image import Shape, PalettedShape
from terminedia.values import Directions
try:
    # This is the only Py 3.7+ specific thing in the project
    from importlib import resources
except ImportError:
    resources = None


font_registry = {}

def load_font(font_path, initial=0, last=256, ch1=" ", ch2="#"):

    if font_path == "DEFAULT" and resources:
        data = list(resources.open_text("terminedia.data", "unscii-8.hex"))

    elif font_path == "DEFAULT":
        path = Path(__file__).parent / "data" / "unscii-8.hex"
        data = list(open(path).readlines())

    else:
        data = list(open(font_path).readlines())

    font = {}

    for i, line in enumerate(data[initial:last], initial):
        line = line.split(":")[1].strip()
        line = binascii.unhexlify(line)
        char  = "\n".join(f"{bin(v).split('b')[1]}".zfill(8)  for v in line)
        char = char.replace("0", ch1).replace("1", ch2)
        font [chr(i)] = char

    return font


def render(text, font=None, shape_cls=PalettedShape, direction=Directions.RIGHT):
    if font is None:
        font = "DEFAULT"

    if font not in font_registry:
        font_registry[font] = load_font(font)

    font = font_registry[font]
    phrase = [shape_cls(font[chr]) for chr in text]
    if len(text) == 0:
        return shape_cls.new((0,0))
    elif len(text) == 1:
        return phrase[0]
    return phrase[0].concat(*phrase[1:], direction=direction)



