import asyncio
import time

import terminedia
from terminedia.events import QuitLoop, Subscription, KeyPress
from terminedia.screen import Screen
from terminedia.input import KeyCodes
from terminedia.utils import contextkwords


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
        from terminedia import context

    break_loop = Subscription(QuitLoop)
    context.screen = screen

    screen.accelerate()

    with terminedia.keyboard, terminedia.mouse, screen:
        while not break_loop:

            frame_start = time.time()
            await asyncio.sleep(0)
            screen.update()
            frame_wait = max(0, (1 / context.fps) - (time.time() - frame_start))
            await asyncio.sleep(frame_wait)


def _refresh_line(text, pos, max_pos, backspace=0):
    delete_back = '\b' * backspace
    text = ''.join(text)
    clear = " " * ((max_pos - pos) - len(text) + backspace)
    move_back = (len(text) + len(clear)) * "\b"
    terminedia.print(delete_back, text, clear, move_back, sep="", end="", flush=True)


@contextkwords
async def ainput(prompt="", maxwidth=None, insert=True):
    result = []
    if prompt:
        terminedia.print(prompt, end="", flush=True)
    with terminedia.keyboard:
        keyboard_events = Subscription(KeyPress)
        max_pos = pos = 0
        async for event in keyboard_events:
            print_code = key = event.key
            if key == KeyCodes.ENTER:
                keyboard_events.kill()
            allow_print = True
            if key:
                if key == KeyCodes.RIGHT:
                    if pos < len(result) and (maxwidth is None or pos < maxwidth - 1):
                        pos += 1
                    else:
                        allow_print = False
                elif key == KeyCodes.LEFT:
                    if pos > 0:
                        pos -= 1
                    else:
                        allow_print = False
                elif key == KeyCodes.DELETE:
                    if len(result) > pos:
                        del result[pos]
                        _refresh_line(result[pos:], pos, max_pos)
                    allow_print = False
                elif key == KeyCodes.BACK and pos > 0:
                    pos -= 1
                    del result[pos]
                    _refresh_line(result[pos:], pos, max_pos + 2, backspace=1)
                    allow_print = False
                elif key in KeyCodes.codes:
                    allow_print = False

            allow_new_char =  maxwidth is None or len(result) < maxwidth
            if key not in KeyCodes.codes:
                if allow_new_char and pos == len(result):
                    result.append(key)
                elif insert and allow_new_char: # (and pos <= len(result):)
                    result.insert(pos, key)
                    _refresh_line(result[pos:], pos + 1, max_pos)
                elif not insert and pos < len(result):
                        result[pos] = key
                        pos += 1
                else:
                    allow_print = False
                if allow_new_char:
                    pos += 1

            if allow_print:
                terminedia.print(print_code, end="", flush=True)
            max_pos = max(max_pos, pos)


    return ''.join(result)






