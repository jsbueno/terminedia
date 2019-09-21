import click
from ast import literal_eval

import terminedia.values
from terminedia import Screen, pause, DEFAULT_FG

@click.command()
@click.argument("text", default="terminedia")
@click.option("size", "--size", "-s", default=4, help="Block height for char. Allowed values: 1, 4 or 8")
@click.option("position", "--pos", "-p", default="0,0", help="Char grid position to render text. Default '0,0'")
@click.option("color", "--color", "-c", default="DEFAULT_FG", help="""\
Color to use for rendering. Use 3 comma separated numbers as RGB (ex. '-c 255,0,0'). Defaults to default terminal color\
""")
@click.option("clear", "--clear", "-l", flag_value=True, help="Clears the screen")
def main(text, position, size, color, clear):
    """Terminedia example for rendering large text characters
    """
    position = literal_eval(f"({position})")
    color = literal_eval(f"({color})") if color.count(",") >= 2 else getattr(terminedia.values, color)
    with Screen(clear_screen=clear) as sc:
        sc.context.color = color
        sc.text[size].at(position, text)
        pause()


if __name__ == "__main__":
    main()
