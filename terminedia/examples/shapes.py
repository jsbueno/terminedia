import time

import click

from terminedia import Screen, realtime_keyb, inkey, DEFAULT_FG
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

c_map = {
    '*': DEFAULT_FG,
    '#': (.5, 0.8, 0.8),
    '!': (1, 0, 0),
    '%': (1, 0.7, 0),
}


@click.command()
@click.option("shape", "--shape1", flag_value=shape1, default=True, help="Default small ship")
@click.option("shape", "--shape2", flag_value=shape2, help="Large ship, using colors")
@click.option("shape", "--custom", type=str, help="""
              Custom shape. Use '*' to set a pixel, '\\n' for a new-line.
              Pad all sides with spaces for best results
              """)
@click.option("high", "--high", flag_value=True, help="Use high-resolution 1/4 block pixels")
@click.option("braille", "--braille", flag_value=True, help="Use braille characters as high-resolution 1/8 block pixels")
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
    size_ =   (shape.find("\n") if "\n" in shape else 1), shape.count("\n")
    #size_ = 13, 7
    factor = 1
    #if shape == shape2:
    #    size_ = 21, 12
    with realtime_keyb(), Screen(clear_screen=False) as scr:
        parent_scr = scr
        if high:
            scr = scr.high
            factor = 2
        elif braille:
            scr = scr.braille
            factor = 2

        x = scr.get_size()[0] // 2 - 6
        y = 0
        while True:
            key = inkey()
            if key in (K.ESC, "q"):
                break

            with parent_scr.commands:

                scr.draw.rect((x, y), rel=size_, erase=True)

                x += factor * ((key == K.RIGHT) - (key == K.LEFT))
                y += factor * ((key == K.DOWN) - (key == K.UP))

                scr.draw.blit((x, y), shape, **({"color_map": c_map} if shape == shape2 else {}))

            time.sleep(1/30)


if __name__ == "__main__":
    main()
