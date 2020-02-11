"""
Demonstrates how to add a Sprite to the Screen, instantiating
it from a list of shape sizes, and use the
initial "tick" system to cycle through the sprite shapes
"""

import time
import terminedia as TM

K = TM.KeyCodes


def setup():
    sc = TM.Screen()
    sc.data.sprites.append([(6, 3)] * 5)
    colors = "white green yellow red purple".split()

    for shape, color in zip(sc.data.sprites[0].shapes, colors):
        shape.context.color = color
        shape.draw.fill()
    sc.data.sprites[0].pos = (10,10)
    sc.data.sprites[0].active = True

    return sc


def iterate(sc):
    with TM.keyboard():
        while True:
            if TM.inkey() == K.ESC:
                break
            sc.update()
            time.sleep(0.1)


def main():
    sc = setup()
    iterate(sc)


if __name__ == "__main__":
    main()