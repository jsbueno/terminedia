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

main()
