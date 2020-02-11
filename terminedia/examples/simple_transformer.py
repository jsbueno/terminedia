import terminedia as TM
from  terminedia.transformers import dilate_transformer

sc = TM.Screen()
a = TM.shape((80,15))
a.text[8].at((0,0), "bla")
b  = TM.Sprite(a)
b.active=True
sc.data.sprites.append(b)
b.pos = (5,5)
a.context.transformers.append(dilate_transformer)
sc.update()
