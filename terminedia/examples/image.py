from pathlib import Path

import click

from terminedia import shape, Screen, pause


basepath = Path(__file__).parent
default_image = basepath / "moon_bin_bw.pgm"


phrase = "TERMINEDIA EXAMPLE"



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
        for img_path in image_paths:
            img = shape(img_path)
            scr.draw.blit((0,0), img)
            scr.context.color = 1, 0, 0
            # scr.print_at((img.width // 2 - len(phrase) // 2, img.height // 2,), phrase)
            pause()
            scr.clear()


if __name__ == "__main__":
    import sys
    main(sys.argv[1:])
