import asyncio
import time

import terminedia
from terminedia.events import QuitLoop, Subscription, KeyPress
from terminedia.screen import Screen


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


async def ainput(prompt="", maxwidth=None, insert=False):
    result = ""
    if prompt:
        terminedia.print(prompt, end="", flush=True)
    with terminedia.keyboard:
        keyboard_events = Subscription(KeyPress)
        async for event in keyboard_events:
            key = event.key
            if key == "\r":
                keyboard_events.kill()
            if key:
                terminedia.print(key, end="", flush=True)
            if key not in terminedia.input.KeyCodes.codes:
                result += key
                # TODO: handle cursor movement and insertion

    return result






