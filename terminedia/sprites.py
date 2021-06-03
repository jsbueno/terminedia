from collections.abc import Sequence
from numbers import Real
from pathlib import Path
import weakref

from terminedia.transformers import TransformersContainer
from terminedia.utils import  HookList, Rect, V2, get_current_tick
from terminedia.values import EMPTY, TRANSPARENT


tags = dict()


class Sprite:
    """Sprites are meant to be associated with Shapes

    They themselves contain a collection of shapes, a position relative to the
    top-left or center location of the base shape on the host shape.

    When the base shape is rendered (using blit or screen.update), if the sprite is active,
    corresponding pixels  are picked from the sprite. Thus, a sprite can be moved around the
    host shape by changes to its `.pos` attribute,  without interfering with the host's
    contents.

    If more than one shape is in the collection, there is always one
    active shape selected by the current "tick" mod self.tick_cycle:
    this provides a descomplicated way to have an animated shape;
    ("tick" is a global value increased by one each time Screen.update() is called)

    (Each shape on a sprite can, in turn, be host to text planes, and other
    sprites as needed)

    """
    def __init__(self, shapes, pos=(0,0), active=True, tick_cycle=1, anchor="topleft", alpha=True):
        from terminedia.image import Shape
        self.shapes = self._check_and_promote(shapes)
        self.pos = pos
        self.active = active
        self.tick_cycle = tick_cycle
        self.anchor = anchor
        self.transformers = TransformersContainer()
        self.dirty_previous_rect = self.rect
        for shape in self.shapes:
            shape._owner_sprite = weakref.ref(self)
            if alpha:
                shape.spaces_to_transparency()

    def _check_and_promote(self, shape_specs):
        """called at initialization to try to promote any object that is not a Shape
        to a Shape.

        """
        from terminedia.image import shape, Shape, FullShape
        if isinstance(shape_specs, (str, Path, Shape, V2)) or (isinstance(shape_specs, Sequence) and len(shape_specs) == 2 and isinstance(shape_specs[0], Real)):
            shape_specs = [shape_specs]
        shapes = []
        for index, item in enumerate(shape_specs):
            if not isinstance(item, Shape):
                item = shape(item)
            if not isinstance(item, FullShape):
                item = FullShape.promote(item)
            shapes.append(item)
        return shapes

    @property
    def active(self):
        return self.__dict__["active"]

    @active.setter
    def active(self, value):
        self.__dict__["active"] = value
        # self.dirty_previous_rect = None
        if getattr(self, "owner", None):
            self.owner.dirty_registry.push((get_current_tick(), self.rect, None))

    @property
    def pos(self):
        return self._pos

    @pos.setter
    def pos(self, value):
        if getattr(self, "owner", None):
            self.owner.dirty_registry.push((get_current_tick(), self.rect, None))
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

    @property
    def absrect(self):
        rect = self.rect
        shape = self.owner
        while shape:
            if hasattr(shape, "_owner_sprite"):
                sp = shape._owner_sprite()
                if sp is None:
                    break
                rect += sp.pos
                shape = sp.owner if hasattr(shape, "owner") else None
            else:
                break
        return rect

    @property
    def dirty_rects(self):
        changed_rect = self.rect != self.dirty_previous_rect
        transformer_using_tick = any("tick" in transformer.signatures for transformer in self.transformers)
        if changed_rect or transformer_using_tick:
            dirty = {(self.rect - self.rect.c1).as_tuple}
        else:
            dirty = self.shape.dirty_rects

        self.dirty_previous_rect = self.rect
        return dirty

    def owner_coords(self, rect, where=None):
        if not isinstance(rect, Rect):
            rect = Rect(rect)
        if not where:
            where = self.rect
        return Rect(where.c1 + rect.c1, width=rect.width, height=rect.height)

    def get_at(self, pos=None, container_pos=None, pixel=None):
        # TODO: pixel to be used when there are combination modes/translucency
        if container_pos:
            if self.anchor == "topleft":
                pos = container_pos - self.pos
            else:
                pos = container_pos - self.rect.c1
        pixel = self.shape[pos]
        if self.transformers:
            pixel = self.transformers.process(self.shape, pos, pixel)
        return pixel

    def kill(self):
        if getattr(self, "owner", None):
            self.owner.sprites.remove(self)


class SpriteContainer(HookList):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.killed_sprites = []

    def insert_hook(self, item):
        if not isinstance(item, Sprite):
            item = Sprite(item)
        item.owner = self.owner
        return item

    def get_at(self, pos, pixel=None):
        # TBD:unit test sprite layering
        pcls = type(pixel)
        for sprite in reversed(self.data):
            if not sprite.active:
                continue
            if pos in sprite.rect:
                new_pixel = sprite.get_at(container_pos=pos, pixel=pixel)
                if any(comp is TRANSPARENT for comp in new_pixel):
                    pixel = [c_orig if c_new is TRANSPARENT else c_new for c_orig, c_new in zip(pixel, new_pixel)]
                else:
                    pixel = new_pixel
        return pixel if isinstance(pixel, pcls) else pcls(*pixel)

    def add(self, item, pos=(0,0), active=True, tick_cycle=1, anchor="topleft", alpha=True):
        if not isinstance(item, Sprite):
            item = Sprite(item, pos, active, tick_cycle, anchor, alpha=alpha)
        self.append(item)
        return item

    def remove(self, sprite):
        self.killed_sprites.append(sprite.rect)
        super().remove(sprite)
        sprite.owner = None
