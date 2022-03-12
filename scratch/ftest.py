import asyncio
import terminedia as TM

def main():
    sc = TM.Screen()
    sp1 = sc.sprites.add((40, 10))
    done = False
    def ready(*args):
        nonlocal done
        done = True
    with sc, TM.keyboard, TM.mouse:

        picker = TM.widgets.FileSelector(sp1, callback=ready)
        while not done:
            sc.update()


    print(picker.value)


def done(widget, event):
    sc.clear()
    TM.print_at((0, 0), widget.value)
    TM.events.Event(TM.events.QuitLoop)

def main_entry():
    global sc
    sc = TM.Screen()
    e = TM.widgets.Entry(sc, pos=(0,0), width=5, text_plane=4, enter_callback=lambda w, event: print(w.value), text_size=10, value="012345678", offset=4)
    loop = asyncio.run(TM.terminedia_main(sc))



if __name__ == "__main__":
    main_entry()
