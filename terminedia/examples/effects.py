import click

import terminedia as TM

@click.command()
@click.argument("phrases", required=False, nargs=-1)
def main(phrases):
    if not phrases:
        phrases = ["Hello World!"] * len(TM.Effects)

    with TM.Screen() as sc:
        for line, (phrase, effect) in enumerate(zip(phrases, TM.Effects)):
            sc.context.effects = TM.Effects.none

            sc.print_at((0, 2* line), f"{effect.name}: ")
            sc.context.effects = effect
            sc.print(phrase)
        TM.pause()


if __name__ == "__main__":
    main()
