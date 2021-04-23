import asyncio
import time

import terminedia
from terminedia.events import QuitLoop, Subscription, KeyPress
from terminedia.screen import Screen
from terminedia.input import KeyCodes


async def terminedia_main(screen=None, context=None):
    """Terminedia mainloop - Framework support for interactive applications and animations

    Usage:
    ...
    import asyncio
    from terminedia import terminedia_main

    ## setup screen, elements and event callback functions
    screen = terminedia.Screen()
    ...

    asyncio.run(terminedia_main, screen)
    #EOF

    Any code can dispatch an events.EndLoop event to exit the
    automatic mainloop update.

    (history: up to now (4/2021) anyne developing using terminedia
    was suppsed to code their own loop, and call screen.update()
    on each frame)


    """


    if screen is None:
        screen = Screen()
    if context is None:
        from terminedia import root_context as context

    break_loop = Subscription(QuitLoop)

    while not break_loop:

        frame_start = time.time()
        await asyncio.sleep(0)
        screen.update()
        await asyncio.sleep(1 / context.fps)


async def ainput(prompt="", maxwidth=None, insert=True):
    result = []
    if prompt:
        terminedia.print(prompt, end="", flush=True)
    with terminedia.keyboard:
        keyboard_events = Subscription(KeyPress)
        pos = 0
        async for event in keyboard_events:
            key = event.key
            if key == KeyCodes.ENTER:
                keyboard_events.kill()
            allow_print = True
            if key:
                if key == KeyCodes.RIGHT:
                    if maxwidth is not None and pos < len(result):
                        pos += 1
                    else:
                        allow_print = False
                if key == KeyCodes.LEFT:
                    if pos > 0:
                        pos -= 1
                    else:
                        allow_print = False
                #if key == KeyCodes.DELETE:
                    #if len(result) > pos:
                        #del result[pos]
                if key in {KeyCodes.UP, KeyCodes.DOWN}:
                    allow_print = False

                if allow_print:
                    terminedia.print(key, end="", flush=True)
            if key not in KeyCodes.codes:
                if insert and (maxwidth is None or len(result) < maxwidth):
                    result.insert(pos, key)
                    pos += 1
                elif not insert:
                    if pos == len(result) and (maxwidth is None or len(result) < maxwidth):
                        result.append(key)
                    elif pos < len(result):
                        result[pos] = key


    return ''.join(result)






