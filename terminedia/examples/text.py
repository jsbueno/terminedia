import click
from ast import literal_eval

import terminedia.values
from terminedia import Screen, pause, DEFAULT_FG, Color


@click.command()
@click.argument("text", default="terminedia")
@click.option(
    "size",
    "--size",
    "-s",
    default="4",
    help="Block height for char. Allowed values: 1, 2, 3, 4, 8 or 'square'",
)
@click.option(
    "position",
    "--pos",
    "-p",
    default="0,0",
    help="Char grid position to render text. Default '0,0'",
)
@click.option(
    "font",
    "--font",
    "-f",
    default="",
    help="""Use one of the 8x8 builtin UNSCII fonts: "fantasy", "mcr", "thin" """,
)
@click.option(
    "color",
    "--color",
    "-c",
    default="default",
    help="""\
Color to use for rendering. Use 3 comma separated numbers as RGB (ex. '-c 255,0,0'). Defaults to default terminal color\
""",
)
@click.option("clear", "--clear", "-l", flag_value=True, help="Clears the screen")
def main(text, position, size, color, clear, font):
    """Terminedia example for rendering large text characters
    """
    position = literal_eval(f"({position})")
    if color == "default":
        color = DEFAULT_FG
    else:
        color = Color(literal_eval(f"({color})") if color.count(",") >= 2 else color)
    if size.isdigit():
        size = int(size)
    elif size == "square":
        size = (8, 4)
    with Screen(clear_screen=clear) as sc:
        sc.context.color = color
        sc.context.font = font
        sc.text[size].at(position, text)
        pause()


if __name__ == "__main__":
    main()
