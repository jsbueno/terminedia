"""Ready to use Transformer classes

These should be appended to a Sprite's "transformers" list,
to generate several effects.

Over time, more 'transformers' should be made
available here.

'Table' transformers
---------------------

The transformers with "table" in the name will use
a convolution operation on a 3x3 matrix around any displayed
character and replace those by Unicode line drawing
characters.

```python
import terminedia as TM
block = TM.shape((10,10))
block.draw.rect((1,1, 9, 9))
sc = TM.Screen()
sp1 = sc.data.sprites.add(block, active=True)
sp1.transformers.append(TM.transformers.library.box_light_table_transformer)
block.draw.line((1, 4),(8, 4))
sc.update()

for variant_name, trans in TM.transformers.library.box_transformers.items():
    sp1.transformers.clear()
    sp1.transformers.append(trans)
    sc.text[1].at((0, 15), variant_name + "               ")
    sc.update()
    TM.pause()

```
"""
import re

from terminedia import values
from terminedia.utils import LazyDict, Color

from . import Transformer, KernelTransformer, kernel_dilate
from ._kernel_table_ascii import kernel as kernel_table_ascii
from ._kernel_table_unicode_square import kernel as pre_kernel_table_unicode_square


def _kernel_table_factory(kernel, expr=("-", "-")):
    new_kernel = {}

    candidates = [expr[1], expr[1].split()[0], expr[0]]

    if "ARC" in expr[1]:
        candidates.insert(1, "LIGHT ARC")
        candidates.insert(1, expr[1].replace("ARC ", ""))

    for key, name in kernel.items():
        for replacement in candidates:
            new_name = re.sub(expr[0], replacement, name) if expr else name
            try:
                new_kernel[key] = f"\\N{{{new_name}}}".encode().decode("unicode escape")
            except UnicodeDecodeError:
                # character with replaced name does not exist
                pass
            else:
                break

    return KernelTransformer(new_kernel, mask_diags=True)


ascii_table_transformer = KernelTransformer(kernel_table_ascii)
box_light_table_transformer = _kernel_table_factory(pre_kernel_table_unicode_square)

box_transformers = LazyDict()

for variant in (
    "LIGHT",
    "DOUBLE",
    "HEAVY",
    "LIGHT DOUBLE DASH",
    "LIGHT TRIPLE DASH",
    "LIGHT QUADRUPLE DASH",
    "HEAVY DOUBLE DASH",
    "HEAVY TRIPLE DASH",
    "HEAVY QUADRUPLE DASH",
    "LIGHT ARC",
    "LIGHT ARC DOUBLE DASH",
    "LIGHT ARC TRIPLE DASH",
    "LIGHT ARC QUADRUPLE DASH",
):
    box_transformers[variant.replace(" ", "_")] = lambda variant=variant: _kernel_table_factory(
        pre_kernel_table_unicode_square, ("LIGHT", variant)
    )

box_transformers["ASCII"] = ascii_table_transformer

class ThresholdTransformer(Transformer):

    def __init__(self, threshold=0.5, invert=True, foreground=values.DEFAULT_FG, **kwargs):
        super().__init__(foreground=foreground, **kwargs)
        self.threshold = threshold
        self.invert = invert

    def char(self, char, foreground):
        if not isinstance(foreground, Color):
            foreground = Color(foreground)
        if (foreground.value >= self.threshold) ^ self.invert:
            return char
        return values.EMPTY


class AddAlpha(Transformer):
    def pixel(self, pixel):
        value = values.TRANSPARENT if pixel.value is values.EMPTY else pixel.value
        fg = values.TRANSPARENT if pixel.foreground is values.DEFAULT_FG else pixel.foreground
        bg = values.TRANSPARENT if pixel.background is values.DEFAULT_BG else pixel.background
        eff = values.TRANSPARENT if pixel.effects is values.Effects.none else pixel.effects
        return type(pixel)(value, fg, bg, eff)


AddAlpha = AddAlpha()
Dilate = KernelTransformer(kernel_dilate)

class Shade(Transformer):
    """Will output a character from a given sequence based on the input pixel
    foreground color. The idea is that the highest the color value, The
    most "filled" the character.

    Args:
        - char_gradient: a string sequence with the characters to be used on the mapping
        - grayscale (bool): whether to keep the original hue (and set value to 1) or use the context color for all pixels
        - reverse; whether to reverse the gradient being used

    """

    def __init__(self, char_gradient=' ░▒▓█', grayscale=False, reverse=False):
        self.char_gradient = char_gradient
        self.grayscale = grayscale
        self.reverse = reverse
        super().__init__()

    def foreground(self, foreground, context):
        if self.grayscale:
            return context.foreground
        else:
            if not isinstance(foreground, Color):
                foreground = Color(foreground)
            foreground.value = 1
            return foreground

    def char(self, foreground):
        if not isinstance(foreground, Color):
                foreground = Color(foreground)
        scale = len(self.char_gradient) - 1
        return self.char_gradient[int(round(foreground.value * scale))]

# keep around to play with checker-coarseness at some point:
# scale = ' ░▒🮖▞▚🮕▒▓█'
del Transformer, kernel_table_ascii, variant, LazyDict
