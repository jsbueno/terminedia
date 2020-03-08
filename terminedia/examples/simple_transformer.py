import terminedia as TM
from  terminedia.transformers import ascii_lines_transformer

from  terminedia.transformers.kernel_simple_lines import kernel


sc = TM.Screen()
a = TM.shape((80,15))
a.text[8].at((0,0), "termiwrite", font="thin")
b  = TM.Sprite(a)
b.active=True
sc.data.sprites.append(b)
b.pos = (5,5)
a.context.transformers.append(ascii_lines_transformer)
sc.update()
