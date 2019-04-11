from terminedia import shape, Screen, pause

from pathlib import Path


img = shape(Path(__file__).parent / "moon_ascii_bw.pgm")

with Screen() as scr:
    scr.draw.blit((0,0), img)
    pause()


