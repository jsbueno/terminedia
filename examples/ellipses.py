from terminedia import Screen, realtime_keyb, inkey

def test_ellipses(scr):
    import random
    scr.draw.ellipse((0, 0), (40, 20))
    scr.context.color = 0.5, 0, 1
    scr.high.draw.ellipse((90, 15), (200, 50), True)
    for i in range(20):
        with scr.commands:
            for x in range(0, scr.high.get_size()[0] - 50, 10):
                for y in range(0, scr.high.get_size()[1] - 30, 10):
                    scr.context.color = random.uniform(0, 1), random.uniform(0, 1), random.uniform(0, 1)
                    scr.high.draw.ellipse((x, y), (x + random.randrange(10, 40),  y + random.randrange(5, 20)))
                    inkey()


def main():
    with realtime_keyb(), Screen() as scr:
        test_ellipses(scr)
        while True:
            if inkey() == '\x1b':
                break



if __name__ == "__main__":
    main()

