import terminedia as TM
from  terminedia.transformers import GradientTransformer


sc = TM.Screen()
a = TM.shape((40,4))
a.text[4].at((0,0), "terminedia")
b  = TM.Sprite(a)
b.active=True
sc.data.sprites.append(b)
b.pos = (5,5)
a.context.transformers.append(
    GradientTransformer(TM.ColorGradient([(0, "blue"),(0.5,"white"), (1, "blue")]), TM.Directions.LEFT)
)
sc.update()
