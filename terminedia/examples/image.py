from pathlib import Path

import click

from terminedia import shape, Screen, pause, Effects


basepath = Path(__file__).parent
default_image = basepath / "moon_bin_bw.pgm"


phrase = "Text!"



@click.command()
@click.argument("image_paths", required=False, nargs=-1)
def main(image_paths):
    """Displays an image, given in a path, on the terminal.
    """
    # TODO add more options to control the output,
    # including disabling auto-scaling.
    if not image_paths:
        image_paths = (default_image,)
    with Screen() as scr:
        scr.clear()
        for img_path in image_paths:
            img = shape(img_path, screen=scr)
            with scr.commands:
                scr.draw.blit((0,0), img)
        pause()


if __name__ == "__main__":
    import sys
    main(sys.argv[1:])
