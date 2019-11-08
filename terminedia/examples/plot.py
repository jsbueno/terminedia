import time

import click

from terminedia import Screen, keyboard, inkey, pause


def arange(start, stop=None, step=1):
    if stop is None:
        stop, start = start, 0
    while (start < stop) if step > 0 else (stop < start):
        yield start
        start += step


def test_plot(scr, func, domain=(-2, 2)):

    f = eval(f"lambda x: -({func})")

    w, h = scr.high.get_size()
    scr.context.color = 1, 1, 1

    scr.high.draw.line((0, h // 2), (w - 1, h // 2))
    scr.high.draw.line((w // 2, 0), (w // 2, h - 1))

    scale_x = 1 / (w * 1 / (domain[1] - domain[0]))

    scale_x = 1 / w * (domain[1] - domain[0])
    domain_center = (domain[1] + domain[0]) / 2

    data_points = [f(domain_center + scale_x * (x - w // 2)) for x in range(w)]

    image = min(data_points), max(data_points)
    scale_y = h * 1 / (image[1] - image[0])

    scr.context.color = 1, 0.5, 0
    for x, y in zip(range(w), data_points):
        scr.high.draw.set((x, int(y * scale_y)))

    x_ticks = 10
    y_ticks = 6

    scr.context.color = 0, 1, 0
    for x, x_tick in zip(
        range(0, w, w // x_ticks),
        arange(domain[0], domain[1], (domain[1] - domain[0]) / x_ticks),
    ):
        scr.print_at((x // 2, h // 4 + 1), f"{x_tick:0.02f}")

    for y, y_tick in zip(
        range(0, h, h // y_ticks),
        arange(image[1], image[0], -(image[1] - image[0]) / y_ticks),
    ):

        scr.print_at((w // 4 + 1, y // 2), f"{y_tick:0.02f}")

    scr.print_at(
        (w // 2 - 33, 0), f"f(x) = {func.replace('**3', '³').replace('**2', '²')}"
    )


@click.command()
@click.option(
    "--func",
    type=str,
    help="Function to draw. It should be given as a Python expression using 'x' as a variable.",
)
def main(func=None, domain=(-2, 2)):
    if func is None:
        func = "-2 * x**3 - 3 * x**2 + x - 1"
    with Screen() as scr:
        test_plot(scr, func, domain)
        pause()


if __name__ == "__main__":
    main()
