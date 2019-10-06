from itertools import cycle

import click

import terminedia as TM

@click.command()
@click.argument("phrases", required=False, nargs=-1)
@click.option("clear", "--keep", "-k", flag_value=False, help="Prevents clearing the screen")
@click.option("clear", "--clear", "-l", flag_value=True, default=True, help="Clears the screen")
def main(phrases=(), clear=True):
    if not phrases:
        phrases = ["Hello World! 1234"]

    with TM.Screen(clear_screen=clear) as sc:
        for line, (phrase, effect) in enumerate(zip(cycle(phrases), TM.Effects)):
            sc.context.effects = TM.Effects.none

            sc.print_at((0, line), f"{effect.name}: ")
            sc.context.effects = effect
            sc.print(phrase)
        TM.pause()


if __name__ == "__main__":
    main()
