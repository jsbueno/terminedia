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

```
"""
import re

from . import Transformer, KernelTransformer
from ._kernel_table_ascii import kernel as kernel_table_ascii
from ._kernel_table_unicode_square import kernel as pre_kernel_table_unicode_square


def _kernel_table_factory(kernel, expr=()):
    new_kernel = {}

    for key, name in kernel.items():
        if expr:
            name = re.sub(expr[0], expr[1], name)
        try:
            new_kernel[key] = f"\\N{{{name}}}".encode().decode("unicode escape")
        except UnicodeDecodeError:
            # character with replaced name does not exist
            pass

    return KernelTransformer(new_kernel, mask_diags=True)


ascii_table_transformer = KernelTransformer(kernel_table_ascii)
box_light_table_transformer = _kernel_table_factory(pre_kernel_table_unicode_square)
box_double_table_transformer = _kernel_table_factory(pre_kernel_table_unicode_square, ('LIGHT', 'DOUBLE'))
box_heavy_table_transformer = _kernel_table_factory(pre_kernel_table_unicode_square, ('LIGHT', 'HEAVY'))

del Transformer, KernelTransformer, kernel_table_ascii
