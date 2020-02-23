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
    "high", "--high", flag_value=True, help="Use high-resolution 1/4 block pixels"
)
@click.option(
    "braille",
    "--braille",
    flag_value=True,
    help="Use braille characters as high-resolution 1/8 block pixels",
)
def main(shape, high=False, braille=False):
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
    #shape = shape.rstrip("\n")
    #size_ = V2(
        #(shape.find("\n") if "\n" in shape else len(shape)), shape.count("\n") + 1
    #)
    #factor = 1



    if high:
        fshape = TM.shape((shape.size * 0.5).as_int)
        fshape.high.draw.blit((0,0), shape)
    elif braille:
        fshape = TM.shape((shape.size.x // 2 + shape.size.x % 2, shape.size.y // 4 + int(shape.size.y % 4 != 0) ))
        fshape.braille.draw.blit((0,0), shape)
    else:
        fshape = TM.FullShape.promote(shape)

    last_frame = time.time()
    time_acumulator = 0
    counter = 0

    try:

        with keyboard(), Screen(clear_screen=True) as scr:
        # with Screen(clear_screen=True) as scr:

            x = scr.get_size()[0] // 2 - 6
            y = 0
            pos = V2(x, y)
            sprite = scr.data.sprites.add(fshape, pos, active=True)

            while True:
                key = inkey()
                if key in (K.ESC, "q"):
                    break
                sprite.pos += (
                    ((key == K.RIGHT) - (key == K.LEFT)),
                    ((key == K.DOWN) - (key == K.UP)),
                )

                scr.update()
                current = time.time()
                ellapsed = current - last_frame
                time_acumulator += ellapsed
                counter += 1
                last_frame = current
                pause_time = max(FRAME_DELAY - ellapsed, 0)
                time.sleep(pause_time)
    finally:
        print(f"\nTotal frames: {counter}\nAverage time per frame: {time_acumulator / (counter or 1):.04f}")

if __name__ == "__main__":
    main()
