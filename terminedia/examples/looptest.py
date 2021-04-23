import time


from terminedia import Screen, keyboard, pause, inkey, terminedia_main, context, Rect

import asyncio

from terminedia.events import Subscription, EventTypes, Event
import random

char = "*"


def keys(event):
    global char
    if event.key == "\x1b":
        Event(EventTypes.QuitLoop)
        return
    char = event.key

def draw(event):
    global char
    #char = inkey() or char
    #if char == "\x1b":
        #Event(EventTypes.QuitLoop)
    sc = context.screen
    width, height = sc.size

    sc.data.draw.rect(Rect((random.randint(0, width), random.randint(0,height)), width_height=(20, 10)), color=random.choice("red green yellow blue".split()), char=char, fill=True)


def main():
    s = Subscription(EventTypes.Tick, draw)
    Subscription(EventTypes.KeyPress, keys)
    asyncio.run(terminedia_main())

if __name__ == "__main__":
    main()
