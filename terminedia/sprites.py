from collections.abc import Sequence

from terminedia.utils import  HookList, Rect, V2
from terminedia.values import EMPTY


def get_current_tick():
    """use a coutner global to Screen module, icreased on
    calls to screen.updat()
    """
    from terminedia import context
    return context.ticks if hasattr(context, "ticks") else 0


tags = dict()


class Sprite:
    def __init__(self, shapes=None, pos=(0,0), active=False, tick_cycle=1, anchor="topleft"):
        # from terminedia import shape as shape_factory
        self.shapes = shapes if isinstance(shapes, Sequence) else [shapes]
        self.pos = pos
        self.active = active
        self.tick_cycle = tick_cycle
        self.anchor = anchor

    @property
    def pos(self):
        return self._pos

    @pos.setter
    def pos(self, value):
        self._pos = V2(value)

    @property
    def shape(self):
        tick = get_current_tick()
        return self.shapes[(tick // self.tick_cycle) % len(self.shapes)]

    @property
    def rect(self):
        r = Rect(self.shape.size)
        if self.anchor == "topleft":
            r.left = self.pos.x
            r.top = self.pos.y
        elif self.anchor == "center":
            r.center = self.pos
        return r

    def get_at(self, pos=None, container_pos=None, pixel=None):
        # TODO: pixel to be used when there are combination modes/translucency
        if container_pos:
            if self.anchor == "topleft":
                pos = container_pos - self.pos
            else:
                raise NotImplementedError()
        return self.shape[pos]


class SpriteContainer(HookList):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner

    def insert_hook(self, item):
        item.owner = self.owner
        return item

    def get_at(self, pos, pixel=None):
        for sprite in self.data:
            if not sprite.active:
                continue
            if pos in sprite.rect:
                new_pixel = sprite.get_at(container_pos=pos, pixel=pixel)
                if new_pixel.value != EMPTY:
                    pixel = new_pixel
                    break # TODO: reverse iteration and do not break when partial transparency is implemented
        return pixel

