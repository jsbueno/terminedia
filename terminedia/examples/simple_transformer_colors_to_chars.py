import sys
import terminedia as TM

sc = TM.Screen()

b1 = TM.shape(sys.argv[1] if len(sys.argv) > 2 else "butterfly.jpg", size=(60,30))
b2 = TM.FullShape.promote(b1)
sc.data.sprites.append(b2)
sc.data.sprites[0].active=True

def pixel(pixel):
    fg = TM.Color(pixel.foreground)
    char = "#*o.  "[int((1 - fg.value) * 5)]
    fg.value = 1
    return char, fg, pixel.background, pixel.effects

sc.data.sprites[0].transformers.append(TM.Transformer(pixel=pixel))
sc.update()
