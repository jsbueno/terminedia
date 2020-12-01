import terminedia as TM
import time
import itertools

colors = itertools.cycle(["red", "green", "yellow", "blue", "white", (255, 0, 255), "lime", (255, 0, 0), (128, 128, 128)])
characters = itertools.cycle("█*#O+.")

def clicked(e):
    global lastclick
    if lastclick is None:
        lastclick = e.pos
        sc[e.pos] = "*"
        return
    rect = TM.Rect(lastclick, e.pos)
    rect.c2 += (1, 1)
    sc.draw.rect(rect, char=next(characters), color=next(colors))
    lastclick = None



TM.events.Subscription(TM.events.EventTypes.MouseClick, clicked)

lastclick = None

with TM.input.mouse, TM.Screen() as sc:
    while True:
        key = TM.input.inkey()  #_dispatch=True)
        sc.update()
        time.sleep(0.1)
        if key == "\x1b":
            break

