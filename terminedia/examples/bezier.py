import click

from terminedia import Screen, pause


@click.command()
def main():
    """Drawing API example for plotting a Bezier-curve
    """
    with Screen() as scr:
        scr.high.draw.bezier((0, 0), (0, 40), (100, 40), (100, 10))
        # scr.high.draw.bezier(
        # (100,10), (100, 0), (150, 0), (150, 40)
        # )
        scr.high.draw.bezier((100, 10), (125, 0), (125, 50), (150, 40))
        pause()


if __name__ == "__main__":
    main()
