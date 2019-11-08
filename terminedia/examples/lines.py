import click

from terminedia import Screen, keyboard, inkey


def test_lines(scr):
    w, h = scr.get_size()
    h -= 2
    for y in range(0, h, 5):
        scr.draw.line((0, y), (y * 2, h - 1))


@click.command()
def main():
    """Example for drawing straight lines with the API, using the 1/4 block resolution.
    """
    with keyboard(), Screen() as scr:
        test_lines(scr.high)
        while True:
            if inkey() == "\x1b":
                break


if __name__ == "__main__":
    main()
