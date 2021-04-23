import time


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

def draw(event):
    global char

    sc = context.screen
    width, height = sc.size

    char = inkey() or char
    #if char == "\x1b":
        #Event(EventTypes.QuitLoop)
    sc.data.draw.rect(Rect((random.randint(0, width), random.randint(0,height)), width_height=(20, 10)), color=random.choice("red green yellow blue".split()), char=char, fill=True)


def main():
    s = Subscription(EventTypes.Tick, draw)
    Subscription(EventTypes.KeyPress, keys)
    asyncio.run(terminedia_main())

if __name__ == "__main__":
    main()
