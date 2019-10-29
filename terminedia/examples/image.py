from pathlib import Path

import click

from terminedia import shape, Screen, pause, Effects, V2


basepath = Path(__file__).parent
default_image = basepath / "moon_bin_bw.pgm"


class DummyCtx:
    def __enter__(self):
        pass

    def __exit__(self, *args, **kw):
        pass


@click.command()
@click.argument("image_paths", required=False, nargs=-1)
@click.option(
    "size",
    "--size",
    "-s",
    required=False,
    help="Size of output in <width>x<height> format. Defaults to current terminal size in fullblock color, compensating aspect ratio.",
)
@click.option(
    "output",
    "--output",
    "-o",
    help="Output file: render images to txt + ANSI, instead of displaying it.",
)
@click.option(
    "backend",
    "--backend",
    "-b",
    default="ANSI",
    help="Output file backend: either HTML or ANSI",
)
def main(image_paths, size=None, output="", backend=""):
    """Displays an image, given in a path, on the terminal.
    """
    # TODO add more options to control the output,
    # including disabling auto-scaling.
    if not image_paths:
        image_paths = (default_image,)
    context = scr = Screen(backend=backend)
    if not size:
        size = scr.size
    else:
        size = V2(int(comp) for comp in size.lower().split("x"))
    if output:
        output_file = open(output, "wt", encoding="utf-8")
        context = DummyCtx()
    with context:
        for img_path in image_paths:
            img = shape(img_path, size=size)
            if output:
                img.render(output=output_file, backend=backend)
                output_file.write("\n")
            else:
                scr.clear()
                with scr.commands:
                    scr.draw.blit((0, 0), img)
                pause()


if __name__ == "__main__":
    main()
