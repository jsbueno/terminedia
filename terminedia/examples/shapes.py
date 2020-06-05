import time

import click

import terminedia as TM
from terminedia import Screen, keyboard, inkey, DEFAULT_FG, V2
from terminedia import KeyCodes as K


shape1 = """\
           .
     *     .
    * *    .
   ** **   .
  *** ***  .
 ********* .
           .
"""

shape2 = """\
                    .
     *    **    *   .
    **   ****   **  .
   **   **##**   ** .
   **   **##**   ** .
   **   **##**   ** .
   **************** .
   **************** .
     !!   !!   !!   .
     !!   !!   !!   .
    %  % %  % %  %  .
                   .
"""


FRAME_DELAY = 0.1

c_map = {"*": DEFAULT_FG, "#": (0.5, 0.8, 0.8), "!": (1, 0, 0), "%": (1, 0.7, 0)}


@click.command()
@click.option(
    "shape", "--shape1", flag_value=shape1, default=True, help="Default small ship"
)
@click.option("shape", "--shape2", flag_value=shape2, help="Large ship, using colors")
@click.option(
    "shape",
    "--custom",
    type=str,
    help="""
              Custom shape. Use '*' to set a pixel, '\\n' for a new-line.
              Pad all sides with spaces for best results
              """,
)
@click.option(
    "resolution", "--square", flag_value="square", help="Use square-resolution 1/2 block pixels"
)
@click.option(
    "resolution", "--high", flag_value="high", help="Use high-resolution 1/4 block pixels"
)
@click.option(
    "resolution",
    "--braille",
    flag_value="braille",
    help="Use braille characters as high-resolution 1/8 block pixels",
)
@click.option(
    "clear", "--clear", "-c", flag_value=True, help="Clear screen before showing shapes"
)
@click.option(
    "cycle", "--cycle", "-y", flag_value=True, help="Cycle shape colors using a Transformer"
)
def main(shape, resolution=None, clear=False, cycle=False):
    """Quick example to navigate an string-defined shape through
    the terminal using the arrow keys! Press <ESC> to exit.


    Usage example:
    $ terminedia-shapes --custom="     \\n *** \\n * * \\n *** "

    """
    # Work around apparent bug in click:
    if shape is None:
        shape = shape1
    if "\\n" in shape:
        shape = shape.replace("\\n", "\n")
    original_shape = shape
    shape = TM.shape(original_shape, **({"color_map": c_map} if original_shape == shape2 else {})
)

    shape = TM.FullShape.promote(shape, resolution=resolution)

    last_frame = time.time()
    time_acumulator = 0
    counter = 0

    def cycle_color(foreground, tick):
        if foreground != TM.DEFAULT_FG:
            return foreground
        return TM.Color(["red", "blue", "yellow", "lime"][tick % 4])

    try:

        with keyboard(), Screen(clear_screen=clear) as scr:
        # with Screen(clear_screen=True) as scr:

            x = scr.get_size()[0] // 2 - 6
            y = 0
            pos = V2(x, y)
            sprite = scr.data.sprites.add(shape, pos, active=True)
            if cycle:
                sprite.transformers.append(TM.Transformer(foreground=cycle_color))

            while True:
                key = inkey()
                if key in (K.ESC, "q"):
                    break
                if not clear and key in (K.RIGHT, K.LEFT, K.UP, K.DOWN):
                    scr.data.draw.rect(sprite.rect, erase=True)
                sprite.pos += (
                    ((key == K.RIGHT) - (key == K.LEFT)),
                    ((key == K.DOWN) - (key == K.UP)),
                )

                scr.update()
                current = time.time()
                ellapsed = current - last_frame
                time_acumulator += ellapsed
                counter += 1
                pause_time = max(FRAME_DELAY - ellapsed, 0)
                time.sleep(pause_time)
                last_frame = time.time()
    finally:
        print(f"\nTotal frames: {counter}\nAverage time per frame: {time_acumulator / (counter or 1):.04f}")

if __name__ == "__main__":
    main()
