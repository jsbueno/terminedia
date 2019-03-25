from terminedia import Screen, realtime_keyb

def test_lines(scr):
    w, h = scr.get_size()
    h -= 2
    for y in range(0, h, 5):
        scr.draw.line((0, y), (y * 2, h - 1))

def test_ellipses(scr):
    import random
    scr.draw.ellipse((0, 0), (40, 20))
    scr.context.color = 0.5, 0, 1
    scr.high.draw.ellipse((90, 15), (200, 50), True)
    for i in range(20):
        for x in range(0, scr.high.get_size()[0] - 50, 10):
            for y in range(0, scr.high.get_size()[1] - 30, 10):
                scr.context.color = random.uniform(0, 1), random.uniform(0, 1), random.uniform(0, 1)
                scr.high.draw.ellipse((x, y), (x + random.randrange(10, 40),  y + random.randrange(5, 20)))
                inkey()


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
   %  % %  % %  %  .
                   .
"""

c_map = {
    '*': DEFAULT_FG,
    '#': (.5, 0.8, 0.8),
    '!': (1, 0, 0),
    '%': (1, 0.7, 0),
}


def main():
    with realtime_keyb(), Screen() as scr:
        test_lines(scr.high)
        while True:
            if inkey() == '\x1b':
                break



if __name__ == "__main__":
    main()

