import time

import click

from terminedia import Screen, keyboard, pause, inkey


def test_ellipses(scr, sleep=0.2):
    import random

    # scr.draw.ellipse((0, 0), (40, 20))
    scr.context.color = 0.5, 0, 1
    scr.high.draw.ellipse((90, 15), (200, 50), fill=True)

    scr.context.color = 1, 1, 1
    scr.high.draw.ellipse((90, 15), (200, 50), fill=False)
    scr.high.draw.ellipse((5, 3), (85, 60), fill=False)
    pause()

    import asyncio


    for i in range(30):
        with scr.commands:
            for x in range(0, scr.high.get_size()[0] - 50, 10):
                for y in range(0, scr.high.get_size()[1] - 30, 10):
                    scr.context.color = (
                        random.uniform(0, 1),
                        random.uniform(0, 1),
                        random.uniform(0, 1),
                    )
                    scr.high.draw.ellipse(
                        (x, y),
                        (x + random.randrange(10, 40), y + random.randrange(5, 20)),
                    )
                    inkey()
        time.sleep(sleep)


@click.command()
@click.option(
    "sleep", "--sleep", "-s", default=0.2, help="Seconds to pause after each drawn frame"
)
def main(sleep=0.2):
    """Example and benchmark tests for the drawing API using ellipses
    """
    with keyboard(), Screen() as scr:
        test_ellipses(scr, sleep)
        pause()


if __name__ == "__main__":
    main()
