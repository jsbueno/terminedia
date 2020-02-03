from collections.abc import Sequence

from terminedia.utils import  HookList, Rect, V2

def get_current_tick():
    """use a coutner global to Screen module, icreased on
    calls to screen.updat()
    """
    return 0

class Sprite:
    def __init__(self, shapes=None, pos=(0,0), active=False, tick_cycle=1):
        self.shapes = shapes if isinstance(shapes, Sequence) else [shapes]

    @property
    def shape(self):
        tick = get_current_tick()
        return self.shapes[tick % len(self.shapes)]



    @property
    def rect(self):
        return Rect(self.pos, width_height=self.shape.size)


class SpriteContainer(HookList):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner

    def insert_hook(self, item):
        item.owner = self.owner

    def get_at(self, pos, pixel=None):
        for sprite in self.data:
            if pos in sprite.rect:
                pixel = sprite.get_at(pos, pixel)
        return pixel

