from collections.abc import Sequence


from terminedia.utils import  HookList, Rect, V2, get_current_tick
from terminedia.values import EMPTY


tags = dict()


class Sprite:
    def __init__(self, shapes=None, pos=(0,0), active=False, tick_cycle=1, anchor="topleft"):
        self.shapes = shapes if isinstance(shapes, Sequence) else [shapes]
        self.pos = pos
        self.active = active
        self.tick_cycle = tick_cycle
        self.anchor = anchor
        self._check_and_promote()
        #TODO: think of a practical way of having the same context.transformers
        # set to apply to all shapes in a sprite.
        # without any further implementation, one can use an
        # intermediate Sprite, with a single Shape, which
        # in turn contains another sprite with all the other shapes.
        # The shape context in this intermediate sprite will apply to all others.

        # maybe the most straightforward thing is to just
        # have a #TransformerContainer member in the Sprite class.


    def _check_and_promote(self):
        """called at initialization to try to promote any object that is not a Shape
        to a Shape.

        """
        from terminedia.image import shape, Shape
        for index, item in enumerate(self.shapes):
            if not isinstance(item, Shape):
                self.shapes[index] = shape(item)

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
                pos = container_pos - self.rect.c1
        return self.shape[pos]


class SpriteContainer(HookList):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner

    def insert_hook(self, item):
        if not isinstance(item, Sprite):
            item = Sprite(item)
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

