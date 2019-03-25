import time
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

def main(shape, high=False):
    size_ = 13, 7
    factor = 1
    if shape == shape2:
        size_ = 21, 12
    with realtime_keyb(), Screen() as scr:
        if high:
            scr = scr.high
            factor = 2

        x = scr.get_size()[0] // 2 - 6
        y = 0
        while True:
            key = inkey()
            if key == '\x1b':
                break

            with scr.commands:

                scr.draw.rect((x, y), rel=size_, erase=True)

                x += factor * ((key == K.RIGHT) - (key == K.LEFT))
                y += factor * ((key == K.DOWN) - (key == K.UP))

                scr.draw.blit((x, y), shape, **({"color_map": c_map} if shape == shape2 else {}))

            time.sleep(1/30)


if __name__ == "__main__":
    import sys
    shape = shape2 if "--shape2" in sys.argv else shape1
    high = True if "--high" in sys.argv else False

    main(shape, high)

