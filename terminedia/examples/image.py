from pathlib import Path

import click

from terminedia import shape, Screen, pause, Effects


basepath = Path(__file__).parent
default_image = basepath / "moon_bin_bw.pgm"

@click.command()
@click.argument("image_paths", required=False, nargs=-1)
@click.option("output", "--output", "-o", help="Output file: render images to txt + ANSI, instead of displaying it.")
def main(image_paths, output=""):
    """Displays an image, given in a path, on the terminal.
    """
    # TODO add more options to control the output,
    # including disabling auto-scaling.
    if not image_paths:
        image_paths = (default_image,)
    scr = Screen()
    if output:
        output_file = open(output, "wt", encoding="utf-8")
    else:
        scr.clear()
    for img_path in image_paths:
        img = shape(img_path, screen=scr)
        if output:
            img.render(output=output_file)
            output_file.write("\n")
        else:
            with scr.commands:
                scr.draw.blit((0,0), img)
            pause()


if __name__ == "__main__":
    import sys
    main(sys.argv[1:])
