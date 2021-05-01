import time

import terminedia as TM
from terminedia import Screen, keyboard, pause, inkey, terminedia_main, context, Rect

import asyncio

from terminedia.events import Subscription, EventTypes, Event
import random

"""
Snippet created for the first tests of the async-mainloop usage.

A particular corner case takes place when the keyboard is read both
by event-handlers and explicit calls to "inkey" - code is kept
here so that these ways to read the keyboard can be toggled for
testing purposes.
"""


char = "*"


def keys(event):
    global char
    if event.key == "\x1b":
        Event(EventTypes.QuitLoop)
        return
    # char = event.key

def draw2(event):
    global char

    sc = context.screen
    width, height = sc.size

    char = inkey() or char
    #if char == "\x1b":
        #Event(EventTypes.QuitLoop)
    sc.draw.rect(Rect((random.randint(0, width), random.randint(0,height)), width_height=(20, 10)), color=random.choice("red green yellow blue".split()), char=char, fill=True)


def setup(sc):
    global tr

    class Tr(TM.Transformer):
        current_color = TM.Color("yellow")
        def foreground(self):
            return self.current_color
    tr = Tr()

    shape = TM.shape((60,20))
    sc.sprites.add(shape)
    sc.sprites[0].transformers.append(tr)

    shape.draw.fill(color="red")


def draw(event):
    colors = "red green blue white yellow".split()
    tr.current_color = TM.Color(colors[event.tick // 5  % len(colors)])
    sc.sprites[0].pos=10,10
    if event.tick == 100:
        sh = sc.sprites[0].shape
        sh.clear()
        sh.text[4].at((0,0),"terminedia")


def main():
    global sc
    s = Subscription(EventTypes.Tick, draw)
    Subscription(EventTypes.KeyPress, keys)
    sc = TM.Screen()
    setup(sc)
    asyncio.run(terminedia_main(screen=sc))

if __name__ == "__main__":
    main()
