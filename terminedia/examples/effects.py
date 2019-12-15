from itertools import cycle

import click

import terminedia as TM


@click.command()
@click.argument("phrases", required=False, nargs=-1)
@click.option("effects", "--effect", "-e", required=False, multiple=True,
              help="Choose effects to be displayed")
@click.option(
    "clear", "--keep", "-k", flag_value=False, help="Prevents clearing the screen"
)
@click.option(
    "clear", "--clear", "-l", flag_value=True, default=True, help="Clears the screen"
)
def main(phrases=(), effects=(), clear=True):
    if not phrases:
        phrases = ["Hello World! 1234"]

    if not effects:
        effects = TM.Effects
    else:
        effects = [getattr(TM.Effects, effect, TM.Effects.none) for effect in effects]


    with TM.Screen(clear_screen=clear) as sc:
        for line, (phrase, effect) in enumerate(zip(cycle(phrases), effects)):
            sc.context.effects = TM.Effects.none
            if (len(effects) != 1):
                sc.print_at((0, line), f"{effect.name}: ")
            sc.context.effects = effect
            sc.print(phrase)
        TM.pause()


if __name__ == "__main__":
    main()
