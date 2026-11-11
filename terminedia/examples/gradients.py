import terminedia as TM
sc = TM.Screen()
u = sc.update
width = sc.width

sp1 = TM.Sprite((width,1))
sc.shape.sprites.append(sp1)
sp1.pos = (0, 5)
sp1.shape.draw.fill()
u()
sp2 = TM.Sprite((width,1))
sc.shape.sprites.append(sp2)
sp2.pos = (0, 10)
sp2.shape.draw.fill()
#shows two white ribbons
u()

# RGB
gr1  = TM.ColorGradient([(0,  "red"), (1, "blue")])

# HSV
gr2  = TM.HSVColorGradient([(0, "red"), (1, "blue")], direction="cw")

sp1.transformers.append(TM.transformers.GradientTransformer(gr1))
sp2.transformers.append(TM.transformers.GradientTransformer(gr2))

u()
