import asyncio
import terminedia as TM

import terminedia.widgets as W

TM.DEBUG = True
def text(sc):

    entry2 = TM.widgets.Text(sc, size=(3, 3), pos=(26, 0), text_plane="square", cancellable=True, border=True, text_size=18)
    entry6 = TM.widgets.Entry(sc, 5, pos=(0, 0), text_plane="normal", cancellable=True, border=True, text_size=10)
    entry6.shape.context.color = (255,128,0)
    entry7 = TM.widgets.Text(sc, size=(6, 3), pos=(26, 14), text_plane="high", cancellable=True, border=True, text_size=18, direction=TM.Directions.DOWN)
    entry7.shape.context.color = (0,128,255)
    entry7.shape.context.direction = TM.Directions.DOWN
    entry7.shape.text["high"].reset_marks(layout=TM.text.planes.Layouts.vertical)

    target = entry2
    def bla(e):
        sc.draw.rect((0, 10, 40,15), char=".", fill=True)
        sc[0,10] = f"{target.value:40s}"
        target.focus=True
        # import os;os.system("reset");breakpoint()
    b = TM.widgets.Button(sc, "check", pos=(0,4), command=bla, border=True)
    b2 = TM.widgets.Button(sc, "clear", pos=(0,7), command=lambda e: target.clear(), border=True)
    target.focus=True
    TM.context.fps=15

def main():
    sc = TM.Screen()
    text(sc)
    asyncio.run(TM.terminedia_main(screen=sc))

if __name__ == "__main__":
    main()

