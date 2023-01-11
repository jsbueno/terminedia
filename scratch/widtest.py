import asyncio
import terminedia as TM

import terminedia.widgets as W

sc = None
counter =0


def done(entry, event=None):
    global counter
    sc.text[1][0,0] = TM.text.escape(str(entry.value))
    sc.update()
    entry.kill()
    counter += 1
    if counter == 3:
        TM.events.Event(TM.events.QuitLoop)

def sshaped_area(shape, plane=1):
    width = shape.text[plane].size.x - 1
    for y in range(0, shape.text[plane].size.y, 2):
        shape.text[plane].marks[0, y] = TM.Mark(direction="right")
        shape.text[plane].marks[width, y] = TM.Mark(direction="down")
        shape.text[plane].marks[width, y + 1] = TM.Mark(direction="left")
        shape.text[plane].marks[0, y + 1] = TM.Mark(direction="down")

def init():
    global sc
    sc = TM.Screen()


def text():
    global sc
    sc.update()
    # TM.pause()

    entry1 = W.Text(sc, size=(4, 3), pos=(0, 2), text_plane=4, cancellable=True, border=True)
    entry2 = W.Entry(sc, width=10, pos=(0, 17), enter_callback=done, text_plane=1, border=True)
    #sh = TM.shape(TM.V2(8,5)*4)
    #sshaped_area(sh, 4)
    #sp = TM.Sprite(sh)

    #sh.draw.fill(color="white")
    #sp.active = True
    #sp.pos = (0, 10)
    #entry = W.Text(sc, sprite=sp, pos=(0, 5),esc_callback=done, text_plane=4)
    entry1.shape.context.color = "red"
    entry2.shape.context.color = "red"
    entry2.shape.context.background = (128, 128, 0)
    #entry2.shape.draw.fill(char=" ")
    entry1.sprite.transformers.append(TM.Transformer(background=lambda : (0,0,0)  if not entry1.focus  else (90,90,90) ))
    TM.context.fps=15

    menu1 = W.ScreenMenu(sc, {
            "1": (lambda: sc.draw.rect((30,0,38, 4), fill=True, color="red"), "vermelho"),
            "2": (lambda: sc.draw.rect((30,0,38, 4), fill=True, color="yellow"), "amarelo"),
            "3": ("toggle", "Liga/desliga menu"),
            "4": ({
                    "1": (lambda: sc.draw.rect((30,0,38, 4), fill=True, color="blue"), "azul"),
                    "5": (lambda: sc.draw.rect((30,0,38, 4), fill=True, color="green"), "verde"),
                }, "mais cores"),
            "f": (file_selector, "escolher arquivo")
        },
        columns=3,
    )


#async def file_selector():
    #file = await W.FileSelector()
    #sc.text[1][0,0] = str(file)


def file_done(file):
    # file = await W.FileSelector()
    sc.text[1][0,1] = str(file)


def file_selector():
    xx = sc.sprites.add(TM.shape((40, 15)))

    selector = W.FileSelector(xx, callback=file_done)
    #file = await W.FileSelector()
    #sc.text[1][0,0] = str(file)

def start():
    asyncio.run(TM.terminedia_main(screen=sc))

def click(event):
    sc.text[1][0,0] = f"tick:{event.tick}   [10,0] position: [color: yellow]{event.pos if hasattr(event, 'pos') else '<enter>'}    "

def button():
    global sc
    sc.update()
    # TM.pause()
    # TM.events.Subscription(TM.events.Tick, main)

    button = W.Button(sc, "HELLO", pos=(0, 21), padding=2,command=click, border=True)
    #button.shape.text[1].add_border()

def selector():
    global sc, selector

    options = [(TM.Color(option)) for option in "red green blue white yellow black #0ff #f0f".split()]
    selector = W.Selector(sc, pos=(30, 10), options=options, callback=done, border=True, min_height=3, max_height=5, text_plane=1, min_width=10)

def click2(event):
    sc.text[1][0,0] = f"[color:red]{event.widget.text:^{len(event.widget.text) + 2}s}"


def box():
    global sc, selector
    box = W.VBox(sc, pos=(40, 0), border=True)
    button2 = W.Button(box, "hello2", command=click2, border=True)
    button3 = W.Button(box, "hello3", command=lambda e: selector.insert(1, "click") , border=True)
    text3 = W.Entry(box, width=8)


def main():
    init()
    TM.context.fps = 20
    text()
    button()
    box()
    selector()
    # file_selector()
    start()

if __name__ == "__main__":
    main()
