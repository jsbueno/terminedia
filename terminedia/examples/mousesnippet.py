import terminedia as TM
import time
import itertools

colors = itertools.cycle(["red", "green", "yellow", "blue", "white", (255, 0, 255)])

def clicked(e):
    global lastclick
    if lastclick is None:
        lastclick = e.pos
        return
    sc.draw.rect(lastclick, e.pos, char="#", color=next(colors))
    lastclick = None



TM.events.Subscription(TM.events.EventTypes.MouseClick, clicked)

lastclick = None

with TM.input.mouse, TM.Screen() as sc:
    while True:
        key = TM.input.inkey(_dispatch=True)
        time.sleep(0.1)
        if key == "\x1b":
            break

