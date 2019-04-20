from terminedia import shape, Screen, pause

from pathlib import Path

basepath = Path(__file__).parent


phrase = "TERMINEDIA EXAMPLE"
with Screen() as scr:
    for img_name in "butterfly.jpg", "butterfly_bw.tiff", "butterfly.gif":
        img = shape(basepath / img_name)
        scr.draw.blit((0,0), img)
        scr.context.color = 1, 0, 0
        scr.print_at((img.width // 2 - len(phrase) // 2, img.height // 2,), phrase)
        pause()
        scr.clear()


