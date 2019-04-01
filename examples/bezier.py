from terminedia import Screen, pause


def main():
    with Screen() as scr:
        scr.high.draw.bezier(
            (0,0), (0, 40), (100, 40), (100, 10)
        )
        scr.high.draw.bezier(
            (100,10), (100, 0), (150, 0), (150, 40)
        )
        pause()


if __name__ == "__main__":
    main()
