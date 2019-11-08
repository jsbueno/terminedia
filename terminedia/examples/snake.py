import random
import time

import click

import terminedia
from terminedia import Effects

K = terminedia.KeyCodes
D = terminedia.Directions

APPLE = "\U0001F34E"


class GameOver(BaseException):
    pass


class Snake:

    length_step = 10

    def __init__(self, pos, direction, length=20):
        self.pos = pos
        self.direction = direction
        self.length = length
        self.body = []
        self.remove = []

    def update(self, game):
        x, y = self.pos
        x += self.direction.x
        y += self.direction.y
        self.pos = (x, y)
        self.body.append(self.pos)
        while len(self.body) > self.length:
            self.remove.append(self.body.pop(0))
        self.check_dead(game)
        self.check_item(game)

    def check_item(self, game):
        x, y = self.pos
        x //= 2
        y //= 2
        # The apple emoji is a double width character
        for rx in (x, x - 1):
            if rx < 0:
                continue
            if (rx, y) in game.items:
                game.eat_item((rx, y))

    def check_dead(self, game):
        if game.scr.high.get_at(self.pos):
            raise GameOver()

    def draw(self, scr):
        scr.draw.set(self.pos)
        if self.remove:
            for pos in self.remove:
                scr.draw.reset(pos)
            self.remove[:] = []


@click.command()
def main():
    """Terminedia snake-game!"""

    snake = Snake((2, 2), direction=D.RIGHT)

    with terminedia.Screen() as scr, terminedia.keyboard():
        try:
            game = Game(scr, snake)
            game.run()
        except GameOver:
            pass

    print("Você bateu!\n\n")


class Game:
    def __init__(self, scr, snake):
        self.scr = scr
        self.snake = snake
        self.items = {}
        self.tick = 0
        self.last_item_taken = 0
        self.score = 0
        self.last_score = None

    def run(self):
        self.start_scene()
        while True:
            key = terminedia.inkey()
            if key == K.ESC:
                raise GameOver()

            if key == K.DOWN:
                self.snake.direction = D.DOWN
            elif key == K.UP:
                self.snake.direction = D.UP
            elif key == K.RIGHT:
                self.snake.direction = D.RIGHT
            elif key == K.LEFT:
                self.snake.direction = D.LEFT

            self.snake.update(self)
            self.snake.draw(self.scr.high)

            self.maybe_create_item()
            self.show_status()

            time.sleep(1 / 30)
            self.tick += 1

    def start_scene(self):
        scr = self.scr.high
        width, height = scr.get_size()

        scr.context.color = 1, 0, 1
        scr.draw.line((0, 0), (width - 1, 0))
        scr.draw.line((0, 0), (0, height - 3))
        scr.draw.line((0, height - 3), (width - 1, height - 3))
        scr.draw.line((width - 1, 0), (width - 1, height - 3))
        scr.context.color = terminedia.DEFAULT_FG

    def show_status(self):
        if self.score == self.last_score:
            return
        width, height = self.scr.get_size()
        center = width // 2
        score_str = f"{self.score:<6d}"
        self.scr.print_at(
            (center - 3, height - 1),
            score_str,
            color=(1, 0.5, 0),
            effects=Effects.fullwidth,
        )
        self.last_score = self.score

    def maybe_create_item(self):
        if not (self.tick - self.last_item_taken > 30 and random.random() < 0.05):
            return
        if self.items:
            return

        width, height = self.scr.get_size()
        pos = random.randrange(1, width - 1), random.randrange(1, height - 2)
        self.items[pos] = True
        self.scr.context.color = 1, 0, 0
        self.scr.print_at(pos, APPLE)
        self.scr.context.color = terminedia.DEFAULT_FG

    def eat_item(self, pos):
        item = self.items.pop(pos, None)
        self.scr.reset_at(pos)
        if not item:
            return
        self.snake.length += self.snake.length_step
        self.score += 100
        self.last_item_taken = self.tick


if __name__ == "__main__":
    main()
