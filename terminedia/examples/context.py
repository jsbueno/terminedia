import threading
import time

import click

from terminedia import inkey, realtime_keyb, Screen
from terminedia.utils import init_context_for_thread

from terminedia.screen import LocalContext

def worker(scr, base_x, base_color, num_workers):
    init_context_for_thread(scr.context)
    scr.context.color = 1, 1, 0
    scr.context.background = 0, 0, 0
    scr.draw.line((base_x, 1), (base_x + 20, 1))
    with LocalContext(scr):
        for i in range(10):
            time.sleep(1 / num_workers)
            scr.context.color = tuple(base_color[j] * (i + 1) for j in range(3))
            scr.draw.line((base_x, i + 2), (base_x + 20, i + 2))

    time.sleep(1 / num_workers)
    scr.draw.line((base_x, 12), (base_x + 20, 12))

@click.command()
def main():
    """Example and test for multi-threaded terminal output
    """
    with realtime_keyb(), Screen() as scr:

        scr.context.color = 1, 1, 1

        scr.draw.line((0, 0), (100, 0))
        threads = []
        with LocalContext(scr, color=(1, 0, 0)) as ctx:
            for i, color in enumerate([(.1, 0, 0), (.1, 0.05, 0), (0, .1, 0), (0, .1, .1), (.1, 0, .1)]):
                threads.append(threading.Thread(target=worker, args=(scr, i * 20, color, 5)))
                threads[-1].start()
                time.sleep(1 / 10)

        for t in threads:
            t.join()
        scr.draw.line((0, 13), (100, 13))

        while True:
            key = inkey()
            if key == '\x1b':
                break
            time.sleep(1/30)

if __name__ == "__main__":
    main()

