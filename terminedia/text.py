import binascii
from terminedia import Screen, pause
from importlib import resources


font_registry = {}




def makechars(fontname=None, initial=0, last=256, ch1=" ", ch2="#"):
    chars = {}

    for i, line in enumerate(lines[initial:last], initial):
        line = line.split(":")[1].strip()
        line = binascii.unhexlify(line)
        char  = "\n".join(f"{bin(v).split('b')[1]}".zfill(8)  for v in line)
        char = char.replace("0", ch1).replace("1", ch2)
        chars[chr(i)] = char

    return chars



def main():
    chars = makechars(data, 32, 128)
    chsize = 8
    with Screen() as scr:
        x, y = 12, 8
        for i, letter in enumerate("Hello World!"):
            scr.high.draw.blit((x + chsize * i, y), chars[letter])
        pause()



if __name__ == "__main__":
    data = open("unscii-8.hex").readlines()
    main()


