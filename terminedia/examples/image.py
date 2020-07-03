from pathlib import Path

import click

from terminedia import shape, Screen, pause, Effects, V2
from terminedia.utils import size_in_pixels, size_in_blocks
from terminedia.transformers.library import ThresholdTransformer


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
@click.option(
    "resolution",
    "--resolution",
    "-r",
    type=click.Choice(['square', 'high', 'sextant', 'braille', ''], case_sensitive=False),
    default="",
    help="Text resolution to load image"
)
def main(image_paths, size=None, output="", backend="", resolution=""):
    """Displays an image, given in a path, on the terminal.
    """
    # TODO add more options to control the output,
    # including disabling auto-scaling.
    if not image_paths:
        image_paths = (default_image,)
    context = scr = Screen(backend=backend)
    if not size:
        size = size_in_pixels(scr.size, resolution=resolution)
    else:
        size = V2(int(comp) for comp in size.lower().split("x"))
    if output:
        output_file = open(output, "wt", encoding="utf-8")
        context = DummyCtx()
    with context:
        for img_path in image_paths:
            if not resolution:
                img = shape(img_path, size=size)
            elif resolution == "square":
                img = shape(img_path, size=size, promote=True, resolution=resolution)
            else:
                # For finer than half-block, threshold image prior to rendering
                preliminar_img = shape(img_path, size=size, promote=True)
                img = shape(size_in_blocks(size, resolution))
                preliminar_img.context.transformers.append(ThresholdTransformer(invert=False))
                getattr(img, resolution).draw.blit((0, 0), preliminar_img)

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
