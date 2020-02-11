import terminedia as TM
from  terminedia.transformers import KernelTransformer
from  terminedia.transformers.kernel_simple_lines import kernel




sc = TM.Screen()
a = TM.shape((80,15))
a.text[8].at((0,0), "termiwrite")
b  = TM.Sprite(a)
b.active=True
sc.data.sprites.append(b)
b.pos = (5,5)
a.context.transformers.append(KernelTransformer(kernel=kernel))
sc.update()
