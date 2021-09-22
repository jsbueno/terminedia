import heapq
import logging
import math
import sys
import threading
from abc import ABC, abstractmethod
from collections import namedtuple, ChainMap, deque
from collections.abc import Sequence
from functools import wraps
from inspect import signature
from itertools import chain
from io import StringIO
from pathlib import Path
from weakref import ref, ReferenceType

from terminedia.contexts import Context
from terminedia.sprites import SpriteContainer
from terminedia.subpixels import BrailleChars, HalfChars, SextantChars
from terminedia.unicode import char_width
from terminedia.utils import Color, Rect, V2, LazyBindProperty, get_current_tick, size_in_blocks
from terminedia.unicode_transforms import translate_chars
from terminedia.values import (
    DEFAULT_FG,
    DEFAULT_BG,
    TRANSPARENT,
    CONTEXT_COLORS,
    Directions,
    Effects,
    CONTINUATION,
    EMPTY,
    UNICODE_EFFECTS,
)

logger = logging.getLogger(__name__)

try:
    from PIL import Image as PILImage
except ImportError:
    PILImage = None


#: Special value that can be sent (.send()) during interaction
#: on Shape areas, so that the inner iterator does not go up to
#: the end of a line in the internal buffer is those values
#: will no longer be used. The `drawing.Drawing.blit` method
#: has the code that sends this.
SKIP_LINE = object()

PixelClasses = {}
pixel_capabilities = namedtuple(
    "pixel_capabilities", "value_type has_foreground has_background has_effects"
)


class Pixel(tuple):
    __slots__ = ()

    def __new__(cls, *args, context=None):
        if args and isinstance(args[0], Pixel):
            args = args[0].get_values(context, cls.capabilities)
        return super().__new__(cls, *args)

    def get_values(self, context=None, capabilities=None):
        """Retrieve pixel or context values, according to caller's context and capabilities

        That is, if this pixel provides value as str, fg and bg but no effects,
        and the target accepts value as boolean, fg, and text effects,
        a list with those properties set is generated.

        List is choosen in order to allow further processing of values
        without recreating the container (for example, to replace
        'CONTEXT_COLORS' for the actual colors.

        Although passing a context is optional, if, for generating the target
        values any context values are needed, no further tests are done:
        an AttributeError on the 'None' default context will take place.
        """
        other_capabilities = capabilities or pixel_capabilities(str, True, True, True)
        cap = self.capabilities
        values = []
        if other_capabilities.value_type == cap.value_type:
            values.append(self.value)
        elif other_capabilities.value_type == bool:
            if cap.value_type == str:
                values.append(self.value != EMPTY)
            else:
                # TODO: When implementing alpha colors,
                # a full transparent color should evaluate to 'False'
                values.append(bool(self.value))
        else:
            values.append(context.char if self.value else EMPTY)

        if other_capabilities.has_foreground:
            values.append(self.foreground if cap.has_foreground else context.color)
        if other_capabilities.has_background:
            values.append(self.background if cap.has_background else context.background)
        if other_capabilities.has_effects:
            values.append(self.effects if cap.has_effects else context.effects)

        return values


full_pixel = namedtuple("Pixel", "char fg bg effects")


def pixel_factory(
    value_type=str,
    has_foreground=True,
    has_background=False,
    has_effects=False,
    translate_dots=True,
):
    """Returns a custom pixel class with specified capabilities

    Args:
        value_type(str or bool): Data type returned by the pixel
        has_foreground (bool): Whether pixel has a foreground color
        has_background (bool): Whether pixel has a background color
        has_effects (bool): Whether pixel has text-attribute flags

    Created pixel classes or instances are not intended to be directly manipulated -
    instead, they are just a way to convey information from internal images/shapes
    to methods that will draw then.
    """
    PixelBase = globals()["Pixel"]

    capabilities = pixel_capabilities(
        value_type, has_foreground, has_background, has_effects
    )
    if capabilities in PixelClasses:
        Pixel = PixelClasses[capabilities]
    else:
        pixel_tuple = namedtuple(
            "PixelBase",
            (
                ("value",)
                + (("foreground",) if has_foreground else ())
                + (("background",) if has_background else ())
                + (("effects",) if has_effects else ())
            ),
        )

        def __repr__(self):
            return "Pixel({})".format(
                ", ".join(
                    f"{field}={getattr(self, field)!r}" for field in pixel_tuple._fields
                )
            )

        Pixel = type(
            "Pixel",
            (PixelBase, pixel_tuple),
            {"capabilities": capabilities, "__repr__": __repr__, "__slots__": ()},
        )

        if translate_dots or value_type != str:

            @property
            def value(self):
                value = super(Pixel, self).value
                return (
                    (value not in (" ."))
                    if value_type is bool and isinstance(value, str)
                    else value_type(value)
                )

            Pixel.value = value

        PixelClasses[capabilities] = Pixel

    return Pixel


class ShapeApiMixin:
    __slots__ = ()

    @LazyBindProperty(type=Context)
    def context(self):
        return Context()

    @LazyBindProperty
    def draw(self):
        return self._get_drawing()

    @LazyBindProperty
    def text(self):
        return self._get_text()

    @LazyBindProperty
    def high(self):
        return self._get_highres()

    @LazyBindProperty
    def square(self):
        return self._get_highres(block_class=HalfChars, block_width=1, block_height=2)

    @LazyBindProperty
    def braille(self):
        return self._get_highres(block_class=BrailleChars, block_height=4)

    @LazyBindProperty
    def sextant(self):
        return self._get_highres(block_class=SextantChars, block_height=3)

    @LazyBindProperty
    def sprites(self):
        self.has_sprites = True
        return SpriteContainer(self)

    has_sprites = False

    def get_size(self):
        return V2(self.width, self.height)

    @property
    def size(self):
        return self.get_size()

    _data_func = staticmethod(lambda size: [EMPTY * size.x] * size.y)

    def _get_drawing(self):
        from terminedia.drawing import Drawing

        # The 'type(self).__setitem__` pattern ensures __setitem__ is called on the proxy,
        # not on the proxied object.
        return Drawing(
            set_fn=lambda pos, pixel=None: type(self).__setitem__(
                self, pos, pixel if pixel else self.context.char
            ),
            reset_fn=lambda pos: type(self).__setitem__(self, pos, EMPTY),
            get_fn=lambda pos: type(self).get_raw(self, pos),
            size_fn=self.get_size,
            context=self.context,
        )

    def _get_highres(self, **kw):
        from terminedia.drawing import HighRes

        return HighRes(self, **kw)

    def _get_text(self):
        from terminedia.text import TextPlane

        return TextPlane(self)

    def clear(self, transparent=False):
        """Clear the shape with empty spaces.

        params:
            transparent (bool): whether to use special transparency values

        if "transparent" is True, the shape is filled with the
        special TRANSPARENT value that make underlying shape characters, or existing tty content
        unchanged upon blitting.
        """
        with self.context:
            if transparent:
                self.context.char = TRANSPARENT
                self.context.color = TRANSPARENT
                self.context.background = TRANSPARENT
                self.context.effects = TRANSPARENT
                self.context.force_transparent_ink = True
            else:
                self.context.char = EMPTY
            self.draw.fill()
        self.dirty_set()

    def spaces_to_transparency(self):
        from terminedia.transformers.library import AddAlpha
        from terminedia.transformers import TransformersContainer
        ct = TransformersContainer((AddAlpha,))
        with self.context(force_transparent_ink=True):
            ct.bake(self)


#####################
#
#  DIRTY Things:
#  instrumentation to dynamically track modified shape parts, allowing faster frame rendering
#
####################

DirtyNode = namedtuple("DirtyNode", "tick untie rect source")

_none_ref = lambda : None

def _ensure_ref(obj):
    if isinstance(obj, ReferenceType):
        return obj
    if obj is None:
        return _none_ref
    if hasattr(obj.__class__, "__weakref__"):
        return ref(obj)
    return lambda: obj

class OrderedRegistry:
    # TODO: maybe use a linked list

    def __init__(self):
        self.untie = 0
        self.reset()

    def reset(self):
        self.data = []
        self.sources = {}
        self.rects = set()

    def push(self, node):
        if len(node) == 3:
            node = DirtyNode(node[0], self.untie, node[1], _ensure_ref(node[2]))
        else:
            node = DirtyNode(node[0], self.untie, node[2],  _ensure_ref(node[3]))
        self.untie += 1

        t = node.rect.as_tuple
        self.sources.setdefault(t, []).append(node)
        self.rects.add(t)
        heapq.heappush(self.data, node)

    def reset_to(self, node):
        self.reset()
        self.push(node)

    #def clear_left(self, threshold):
        #if not self.data:
            #return
        #counter = 0
        #for node in self.data:
            #if node.tick <= threshold:
                #counter += 1
                #t = node.rect.as_tuple
                #if t in self.sources:
                    #for node2 in self.sources[t]:
                        #source = node2.source()
                        #if hasattr(source, "dirty_clear"):
                            #source.dirty_clear(threshold)
                    #del self.sources[t]

            #else:
                #break
        #self.data[:counter] = []

    def __iter__(self):
        return iter(self.data)

    def __repr__(self):
        return f"Registry <{self.data}>"



DIRTY_TILE_SIZE = 8

class ShapeDirtyMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dirty_registry = OrderedRegistry()
        # Mark all shape as dirty:
        self.dirty_set()
        # collection of all changed pixels:
        self.dirty_pixels = set()
        self.dirty_saved_sprite_rects = set()
        self.dirty_sprite_rects_saved_at = 0

    def dirty_clear(self, threshold=None):
        tick = threshold if threshold is not None else get_current_tick()
        self.dirty_last_clear = tick
        self.dirty_registry.reset()  # clear_left(tick)

        self.dirty_save_current_sprite_rects(tick)
        for sprite in self.sprites:
            sprite.shape.dirty_clear()

    def dirty_save_current_sprite_rects(self, tick):
        self.dirty_sprite_rects_saved_at = tick
        self.dirty_saved_sprite_rects = set()
        if not self.has_sprites:
            return
        for sprite in self.sprites:
            for rect in sprite.dirty_rects:
                self.dirty_saved_sprite_rects.update(sprite.dirty_rects)

    def dirty_set(self, rect=None):
        tick = get_current_tick()
        if rect is None:
            rect = Rect((0, 0), self.size)
        else:
            rect = Rect(rect) if not isinstance(rect, Rect) else rect
        self.dirty_registry.reset_to((tick, rect, None))

    def dirty_update(self):

        tick = get_current_tick()

        # If there is any time-dependant image change, there is no way
        # to predict what changes from one frame to the next - just mark
        # all shape as dirty.
        if any("tick" in sig for transformer in self.context.transformers for sig in transformer.signatures.values()):
            self.dirty_set()
            return

        # Collect rects from sprites
        if self.has_sprites:
            for sprite in self.sprites:
                if not sprite.active:
                    continue

                if any("tick" in sig for transformer in sprite.transformers for sig in transformer.signatures.values()):
                    self.dirty_registry.push((tick, sprite.rect, sprite.shape))
                else:
                    for rect in sprite.dirty_rects:
                        self.dirty_registry.push((tick, sprite.owner_coords(rect), sprite.shape))
            if self.sprites.killed_sprites:
                for rect in self.sprites.killed_sprites:
                    self.dirty_registry.push((tick, rect, None))
                self.sprites.killed_sprites.clear()

        # mark dirty pixels

        tile_size = (DIRTY_TILE_SIZE, DIRTY_TILE_SIZE)
        self_rect = Rect((0, 0), self.size)
        for tile in self.dirty_pixels:
            rect = Rect(tile * DIRTY_TILE_SIZE, width_height=tile_size)
            rect = rect.intersection(self_rect)
            if not rect:
                continue
            self.dirty_registry.push((tick, rect, None))
        self.dirty_pixels = set()

    def dirty_mark_pixel(self, index):
        self.dirty_pixels.add(index // DIRTY_TILE_SIZE)

    @property
    def dirty_rects(self):
        self.dirty_update()
        # on purpose eager approach - the registry might be updated while rendering is taking place
        return self.dirty_registry.rects.copy()

        # return [node.rect for node in self.dirty_registry if self.dirty_registry.sources[node.rect.as_tuple][0].untie == node.untie]

##############
#
#  SHAPE:
#  Base class for all high-level imaging
#
#############

class Shape(ABC, ShapeApiMixin, ShapeDirtyMixin):
    """'Shape' is intended to represent blocks of colors/backgrounds and characters
    to be applied in a rectangular area of the terminal. In this sense, it is
    more complicated than an "Image" that just care about a foreground color
    and alpha value for each pixel position.

    As internal data and rendering intents vary accross desired capabilities,
    there are subclasses to represent each intended use.

    """

    PixelCls = pixel_factory(bool)
    _default_bg = False

    isroot = False

    @classmethod
    def new(cls, size, **kwargs):
        """Creates an empty shape of this class.

        Args:
          - size (2-sequence): width x height of the new shape
          - **kwargs: keyword arguments either to the class empty-data builder
                     (cls._data_func) - e.g. "color" - or for the
                     class' __init__  - e.g. color_map.

        Creates a new empty shape, using given size and keyword parameters,
        which are dispatched as appropriate to build the empty pixel
        values or to the class itself.
        """
        data_parameters = signature(cls._data_func).parameters.keys()
        data_kw = {}
        for name, value in list(kwargs.items()):
            if name in data_parameters:
                data_kw[name] = value
                kwargs.pop(name)
        data = cls._data_func(V2(size), **data_kw)
        return cls(data, **kwargs)

    def load_data(self, data, size=None):
        """Sets internal data from an initial value structure.
        Args:
          - data: data structure containing the elements
                  that will be set to inicial pixel values.
                  Can be a single sequence width x height
                  in size containing all elements
                  to be assigned as pixels, or a
                  height-sized sequence of width-sized sequences.
          - size (V2-like): width x height.

        Used to explictly set the initial values for a shape,
        will usually be called internally as part of the
        Shape initialization. If size is not given, and
        the passed data is 1D in nature, sie is assumed to
        be a single colum (1xN) shape. Strings are split
        at "\n" and will be treated as 2D if multiline.
        """
        if isinstance(data, str):
            data = data.split("\n")
        if not size:
            size = V2(len(data[0]), len(data))
        self.width = w = size[0]
        self.height = h = size[1]

        if len(data) == w * h:
            self.data = list(data)
        else:
            if len(data) != h:
                logger.warn(
                    "Passed size is inconsistent with data shape. Proceeding anyway"
                )
            self.data = []
            for line in data:
                self.data.extend(list(line))
        return self.data

    def get_data_offset(self, pos):
        if pos[0] < 0 or pos[1] < 0 or pos[0] >= self.width or pos[1] >= self.height:
            return None
        return pos[1] * self.width + pos[0]

    def get_raw(self, pos):
        offset = self.get_data_offset(pos)
        if offset is None:
            # TODO: implement abyss_policy in context?
            return EMPTY
        return self.data[offset]

    @abstractmethod
    def __getitem__(self, pos):
        """Common logic to create ShapeViews from slices.

        Pixel data retrieving is implemented in the subclasses.
        """
        if isinstance(pos, Rect):
            roi = pos
        elif isinstance(pos, tuple) and isinstance(pos[0], slice):
            if any(pos[i].step not in (None, 1) for i in (0, 1)):
                raise NotImplementedError("Slice stepping not implemented for shapes")
            roi = Rect(*pos)
        else:
            return None
        return ShapeView(self, roi)

    @abstractmethod
    def __setitem__(self, pos, value):
        """

        Values for each pixel are: character, fg_color, bg_color
        """
        raise NotImplementedError("This is meant as an abstract Shape class")

    def __iter__(self):
        """Iterates over all pixels in Shape

        For each pixel in the image, returns its position,
        its value, the foreground color, background color, and character_effects byte
        """
        for y in range(self.height):
            for x in range(self.width):
                pos = V2(x, y)
                token = yield (pos, self[pos])
                if token is SKIP_LINE:
                    yield None
                    break

    def concat(self, *others, direction=Directions.RIGHT, **kwargs):
        """Concatenates two given shapes side by side into a larger shape.

        Args:
          - other (Shape): Other shape to be concatenated.
          - direction (V2): Side which will be "enlarged" and on which the other shape
                will be placed. Most usefull values are Directions.RIGHT and Directions.DOWN
          - **kwargs: are passed down to the "new" constructor of the resulting shape.

        Creates a new shape combining two or more other shapes. If Shape _allowed_types differ,
        the logic in Drawing.blit will try to cast pixels to the one used in self.
        """
        shapes = (self,) + others

        direction = V2(direction)

        h_size = abs(direction.x) * sum(s.width for s in shapes)
        v_size = abs(direction.y) * sum(s.height for s in shapes)
        new_size = V2(
            max(h_size, max(s.width for s in shapes)),
            max(v_size, max(s.height for s in shapes)),
        )

        new_shape = self.__class__.new(new_size, **kwargs)

        d = direction
        offset = V2(0 if d.x >= 0 else new_size.x, 0 if d.y >= 0 else new_size.y)

        # blit always take the top-left offset corner
        # so, depending on direction of concatenation,
        # offset have to be computed before or after blitting.
        for s in shapes:
            offset += (
                int(s.width * d.x if d.x < 0 else 0),
                int(s.height * d.y if d.y < 0 else 0),
            )
            new_shape.draw.blit(offset, s)
            offset += (
                int(s.width * d.x if d.x >= 0 else 0),
                int(s.height * d.y if d.y >= 0 else 0),
            )

        return new_shape

    def render(self, output=None, backend="ANSI"):
        """Renders shape contents into a text-output.
          Args:
            - backend (str): currently implemented "ANSI" - output type
            - output(Optional[Union[TextIO, BytesIO]])
          Output:
            ->Optional[Union[str, bytes]]

            Renders shape contents into content that can reprsent the image
            outside terminedia library. That is, if the shape is rendered with "ANSI",
            a text body, with the ESC encoded ANSI sequences for cursor positioning
            embeded will be generated. If this body is subsequnetly printed, the
            image in the Shape is reproduced on the terminal.

            If output is given, it should be a file-like object to which the contents
            of the shape will be written. Binary backends require a binary file. thenmethod returns None.
            If no output is given, the rendered contents are returned.
        """
        backend = backend.upper()
        original_output = output

        self.dirty_set()

        if isinstance(output, (str, Path)):
            output = open(
                output, "w" + ("t" if backend in ("ANSI", "HTML") else "b")
            )

        if not original_output:
            output = StringIO()

        if backend == "ANSI":
            self._render_using_screen(output, backend)
        elif backend == "HTML":
            # FIXME: this somewhat violates some "this module should not know about
            # specific backend stuff (HTML template)."
            # However, the rendering machinnery only knows
            # about incremental rendering, and can't "sandwhich"
            # the final rendering. In any case, the outter HTML template
            # should be configurable in a near term future.
            from terminedia.html import full_body_template

            preamble, post_amble = full_body_template.split("{content}")
            output.write(preamble)
            self._render_using_screen(output, backend)
            output.write(post_amble)
        elif backend == "SNAPSHOT":
            import pickle
            tmp = ShalowShapeRepr(self)
            pickle.dump(tmp, output)
        else:
            raise ValueError(f"Output type {backend!r} not implemented")
        if not original_output:
            return output.getvalue()

    def _render_using_screen(self, output, backend):
        from terminedia.screen import Screen

        if output is None:
            file = StringIO()
        else:
            file = output
        sc = Screen(size=V2(self.width, self.height), backend=backend, interactive=False)
        if backend=="ANSI":
            # generate a relocatable image
            sc.commands.__class__.last_pos = V2(0, 0)
            sc.commands.absolute_movement = False
            sc.commands.force_newlines = True
        # Starts recording all image operations on the internal journal
        sc.commands.__enter__()
        sc.blit((0, 0), self)
        # Ends journal-recording, but without calling __exit__
        # which does not allow passing an external file.
        sc.commands.stop_journal()
        # Renders all graphic ops as ANSI sequences + unicode into file:
        sc.commands.replay(output)
        output.write("\x1b[0m")  # reset all ansi attributes

    def __repr__(self):
        cap = self.PixelCls.capabilities
        bck = cap.has_background
        ftn = cap.has_foreground
        eff = cap.has_effects
        size = self.get_size()
        rep = "".join(
            [
                self.__class__.__name__,
                ": [\n",
                "value_type = " + repr(cap.value_type) + "\n" if cap.value_type else "",
                "foreground\n" if ftn else "",
                "background\n" if bck else "",
                "effects\n" if eff else "",
                f"size = {size.x}, {size.y}\n",
                "]",
            ]
        )
        return rep

    def _resize_data_one(self, new_size, data, fill_value):
        old_size = V2(self.width, self.height)
        lines = [data[i : i + old_size.x] for i in range(0, len(data), old_size.x)]
        new_data = []
        diff = new_size.x - old_size.x
        for y, line in zip(range(new_size.y), lines):

            if diff > 0:
                line.extend([fill_value] * diff)
            elif diff < 0:
                line[diff:] = []
            new_data.extend(line)

        y_diff = new_size.y - old_size.y
        if y_diff > 0:
            new_data.extend([fill_value] * new_size.x * y_diff)

        return new_data

    def _resize_data(self, new_size):
        self.data = self._resize_data_one(new_size, self.data, fill_value=getattr(self.context, "background_char", self.__class__._default_bg))

    def resize(self, new_size):
        new_size = V2(new_size)
        self._resize_data(V2(new_size))
        self.width, self.height = new_size
        if hasattr(self, "rect"):
            self.rect = Rect(new_size)
        self.dirty_set()


# "Virtualsubclassing" - 2 days after I wrote there were no
# practical uses for it.
# With it, "ShapeView" can have "__slots__"
@Shape.register
class ShapeView(ShapeApiMixin):
    __slots__ = ("roi", "original", "_draw", "_high", "_text")

    isroot = False

    def __init__(self, original, roi):
        self.original = original
        self.roi = Rect(roi)

    width = property(lambda s: s.roi.width)
    height = property(lambda s: s.roi.height)
    get_size = lambda s: s.roi.width_height

    def __getitem__(self, index):
        roi = self.roi
        if isinstance(index, Rect):
            return ShapeView(
                self.original,
                Rect(
                    V2.max(roi.c1, (roi.c1 + index.c1)),
                    V2.min((roi.c1 + index.c2), roi.c2),
                ),
            )
        if not 0 <= index[0] < roi.width or not 0 <= index[1] < roi.bottom:
            raise IndexError(f"Value out of limits f{roi.width_height}")
        return self.original[roi.c1 + index]

    def __setitem__(self, index, value):
        roi = self.roi
        if not 0 <= index[0] < roi.width or not 0 <= index[1] < roi.bottom:
            raise IndexError(f"Value out of limits {roi.width_height}")
        self.original[roi.c1 + index] = value

    __iter__ = Shape.__iter__

    def __getattribute__(self, attr):
        # Attributes not proxied in ShapeView
        if attr in {
            "roi",
            "original",
            "width",
            "height",
            "size",
            "get_size",
            "draw",
            "high",
            "text",
            "isroot",
            "_draw",
            "_high",
            "_text",
            "_get_drawing",
            "_get_highres",
            "_get_text",
        }:
            return super().__getattribute__(attr)
        return getattr(self.original, attr)

    def __repr__(self):
        return f"View {self.roi} of {self.original}"


class ValueShape(Shape):

    PixelCls = pixel_factory(bool, has_foreground=True)

    _data_func = staticmethod(lambda size, color=(0, 0, 0): [[color] * size.x] * size.y)
    _allowed_types = (Path, str, Sequence)

    def __init__(self, data, color_map=None, size=None, **kwargs):
        # TODO: make color_map work as a to-pixel palette infornmation
        # to L or I images - not only providing a color palette,
        # but also enabbling an "palette color to character" mapping.
        self.color_map = color_map
        if isinstance(data, self._allowed_types) or hasattr(data, "read"):
            self.load_data(data, size)
        else:
            raise NotImplementedError(f"Can't load shape from {type(data).__name__}")
        super().__init__(**kwargs)

    def __getitem__(self, pos):
        """Composes a Pixel object for the given coordinates.
        """
        v = super().__getitem__(pos)
        if v:
            return v

        color = self.get_raw(pos)
        if color is EMPTY:
            color = self.context.background

        return self.PixelCls(True, color)

    def __setitem__(self, pos, value):
        """
        Values set for each pixel are 3-sequences with an RGB color value
        """
        pos = V2(pos)
        self.dirty_mark_pixel(pos)
        color = value
        if isinstance(value, Pixel):
            v, color = value.get_values(self.context, self.PixelCls.capabilities)
        elif isinstance(value, (int, tuple, Color)):
            color = Color(value)
        elif isinstance(value, str):
            color = self.context.color if value != EMPTY else self.context.background
        self._raw_setitem(pos, color)

    def _raw_setitem(self, pos, color):
        offset = self.get_data_offset(pos)
        if offset is None:
            return
        self.data[offset] = color


class PGMShape(ValueShape):

    PixelCls = pixel_factory(bool, has_foreground=True)
    _allowed_types = (Path, str)

    def load_data(self, file_or_path, size=None):
        """Will load data from a PGM/PPM file.
        Size parameter is ignored
        """
        if not hasattr(file_or_path, "read"):
            file = open(file_or_path, "rb")
        else:
            file = file_or_path
        raw_data = file.read()
        if raw_data[0] == ord(b"P") and raw_data[2] in b"\r\n":
            return self._decode_pnm(raw_data)
        raise NotImplementedError("File format not supported. Try installing 'Pillow' ")

    def _decode_pnm(self, data):
        headers = []
        header_counter = 0
        offset = 0
        while True:
            line_end = data.find(b"\n", offset)
            line = data[offset : line_end + 1]
            offset = line_end + 1
            if line.strip().startswith(b"#"):
                continue
            headers.append(line.strip())
            header_counter += 1
            if header_counter == 3:
                break
        type_, size, max_value = headers

        size = V2(*map(int, size.split()))
        max_value = int(max_value)

        self.width, self.height = size

        type_num = int(type_[1:2])
        if type_num == 2:
            # ASCII encoding, monochronme file
            ascii, values_per_pixel = True, 1
        elif type_num == 3:
            ascii, values_per_pixel = True, 3
        elif type_num == 5:
            ascii, values_per_pixel = False, 1
        elif type_num == 6:
            ascii, values_per_pixel = False, 3
        else:
            raise NotImplementedError(
                f"File not supported. PNM with magic number: {type_.decode!r}"
            )

        data = data[offset:]
        if ascii:
            data = [int(v) for v in data.split()]
        if len(data) != size.x * size.y * values_per_pixel:
            logger.warn("Malformed PNM file. Trying to continue anyway\n")

        data = [value / max_value for value in data]
        if values_per_pixel == 1:
            data = [(value, value, value) for value in data]
        else:
            data = [tuple(data[i : i + 3]) for i in range(0, len(data), 3)]
        self.data = data


class ImageShape(ValueShape):
    """Relies on Python Imaging Library to load and handle image data.

    The internal "data" member is a straighout PIL.Image instance,
    and one is free to use PIL drawing and image manipulation APIs
    to draw on it.

    Important: on instantiating  these shapes, Terminedia will
    try to auto-scale down/resample the image to compensate for
    the aspect-ratio of text imags. Pass the parameter `auto_scale=False`
    to `__init__` or `__new__` to preserve the exact size of the
    PIL Image.

    """

    PixelCls = pixel_factory(bool, has_foreground=True)

    _data_func = staticmethod(
        lambda size, mode="RGB", color=(0, 0, 0): PILImage.new(mode, size, color=color)
    )
    if PILImage:
        _allowed_types = (str, Path, PILImage.Image)

    def load_data(self, file_or_path, size=None, half_height=False):
        """Will load data from an image file using PIL,

        If "size" is not passed, the native image size is used.
        Otherwise it should be a 2-sequence: if both numbers
        are given, that is used as final image size.
        If one component of "size" is "None", the other
        one is used to scale the image, keeping its aspect ratio.

        As due to the nature of character blocks, keeping the aspect ratio can
        lead to a strange 1:2 final display, pass "half_height=True"
        to  keep the same visual aspect ratio for full blocks.
        (hint: you can load the full height and blit
        the resulting shape to a square 1/2 block drawable instead)

        """
        if isinstance(file_or_path, PILImage.Image):
            img = file_or_path
        else:
            img = PILImage.open(file_or_path)
        img_size = V2(img.width, img.height)
        if size is None:
            size = img_size
        else:
            size = V2(size) #- (1, 1)
            if size.x is None:
                size = V2(img_size.x * (size.y / img_size.y)  , size.y).as_int
            elif size.y is None:
                size = V2(size.x, img_size.y * (size.x / img_size.x)).as_int

        pixel_ratio = 1 if not half_height else 0.5

        if size.x != img_size.x or size.y * pixel_ratio != img_size.y:
            ratio_x = size.x / img_size.x
            ratio_y = (size.y / img_size.y) * pixel_ratio
            img = img.resize(size.as_int, PILImage.BICUBIC)

        self.width, self.height = img.width, img.height

        if img.mode in ("L", "P", "I"):
            img = img.convert("RGB")
        elif img.mode in ("LA", "PA"):
            img = img.convert("RGBA")
        self.data = img

    def get_raw(self, pos):
        return self.data.getpixel(pos)

    def _raw_setitem(self, pos, color):
        if isinstance(color, Color):
            color = tuple(color)
        self.data.putpixel(pos, color)

    def resize(self, new_size):
        self.data = self.data.resize(new_size)
        self.width, self.height = self.data.width, self.data.height

    def clear(self, transparent=False):
        img = self.data
        # FIXME: might need to check and upgrade the image to RGBA first
        color = tuple(self.context.background) if not transparent else (0, 0, 0, 0)
        img.paste(tuple(self.context.background), [0,0, img.size[0], img.size[1]])


class PalettedShape(Shape):
    """'Shape' class intended to represent images, using a color-map to map characters to block colors.

    Args:
      - data (multiline string or list of strings): character map to be used as pixels
      - color_map (optional mapping): maps characters to RGB colors.
    This class have no special per pixel values for background or character - each
    block position will read as "False" or "True" depending only on the
    underlying character in the input data being space (0x20) or any other thing.
    """

    foreground = True
    background = False
    arbitrary_chars = False
    effects = False  # FUTURE: support for bold, blink, underline...

    PixelCls = pixel_factory(bool, has_foreground=True)
    _default_bg = False

    def __init__(self, data, color_map=None):
        if color_map is None:
            color_map = {}  # any char != EMPTY or "." paints with current context color
        self.color_map = color_map
        if isinstance(data, (str, list)):
            self.load_paletted(data)
            return
        elif isinstance(data, Path) or hasattr(data, "read"):
            self.load_file(data)
            return
        super().__init__()
        raise NotImplementedError(f"Can't load shape from {type(data).__name__}")

    def load_paletted(self, data):

        # Legacy boolean shape - deservers another, separate, Shape subclass
        # if color_map is None:
        #    self.PixelCls = pixel_factory(bool, has_foreground=False)

        if isinstance(data, str):
            data = data.split("\n")
        self.width = width = max(len(line) for line in data)
        self.height = height = len(data)

        new_data = []
        for line in data:
            # For string-based shapes, '.' is considered
            # as whitespace - this allows multiline
            # strings defining shapes that otherwise would
            # be distorted by program editor trailing space removal.
            new_data.append(f"{{line:<{width}s}}".format(line=line).replace(".", EMPTY))

        self.load_data(new_data, V2(width, height))

    def __getitem__(self, pos):
        """Values for each pixel are: character, fg_color, bg_color, effects.
        """
        v = super().__getitem__(pos)
        if v:
            return v
        char = self.get_raw(pos)
        value = bool(char != EMPTY)

        # TODO: Legacy: when this class doubled as "BooleanShape".
        # (remove comment block when BooleanShape is implemented)
        # if self.color_map:
        # foreground_arg = (self.color_map.get(char, DEFAULT_FG),)
        # else:
        # foreground_arg = ()

        foreground_arg = self.color_map.get(char, CONTEXT_COLORS)
        if not isinstance(foreground_arg, Color):
            foreground_arg = Color(foreground_arg)
        return self.PixelCls(value, foreground_arg)

    def __setitem__(self, pos, value):
        """
        Values set for each pixel are: character - only spaces (0x20) or "non-spaces" are
        taken into account for PalettedShape
        """
        pos = V2(pos)
        self.dirty_mark_pixel(pos)
        type_ = self.PixelCls.capabilities.value_type
        self.raw_setitem(pos, type_(value))

    def _raw_setitem(self, pos, value):
        self.data[pos[1] * self.width + pos[0]] = type_(value)



class PixelDict(ChainMap):
    """Cached ChainMap"""
    def __init__(self, maps=None):
        # Chainmap uses a plain list, still, maps are pilld top-most on the left-side.
        # go figure!
        super().__init__(maps or {})
        self.maps = deque(self.maps)
        self.cache = {}
        self._sentinel = object()

    def __setitem__(self, key, value):
        self.cache[key] = value
        super().__setitem__(key, value)

    def __getitem__(self, key):
        value = self.cache.get(key, self._sentinel)
        if value is self._sentinel:
            value = super().__getitem__(key)
            self.cache[key] = value
        return value

    def clear(self):
        self.maps = [{}]
        self.cache.clear()

    def pop(self):
        self.cache.clear()
        return self.maps.popleft()

    def push(self, map=None):
        if map:
            self.cache.clear()
        self.maps.appendleft(map or {})


class _UNDO_START_MARK:
    pass # sentinel

class _UNDO_IN_PROGRESS_MARK:
    pass # sentinel


class RasterUndo:
    """Controls and offer the API for raster undo-capability

    """
    # FIXME: possibly we will need extracontext.context instead of threading.local
    # (maybe even contextvars.ContextVar could work)
    _undo_registry = threading.local()

    def __init__(self, *args, undo_active=False, max_undo_steps=100, **kw):
        # self.__lock = threading.Lock()
        self.max_undo_steps = max_undo_steps
        self.redo_data = []
        self.undo_active = undo_active
        super().__init__(*args, **kw)

    def __undo_exit(self): #, ext_type, exc_value, tb):
        with self.__lock:
            self.__undo_deph -= 1
            # we don't pop or merge undo-groups: that is up to the app do by calling other functions;

    def undo(self, n=1):
        for i in range(n):
            if len(self.data.maps) <= 1:
                break
            self.redo_data.append(self.data.pop())
        if isinstance(self, ShapeDirtyMixin):
            self.dirty_set()

    def redo(self, n=1):
        for i in range(n):
            if not self.redo_data:
                break
            self.data.maps.push(self.redo_data.pop())
        if isinstance(self, ShapeDirtyMixin):
            self.dirty_set()

    def undo_clear(self, n=1):
        """Merge all pixel data into base, and clear undo history"""
        base = self.data.maps[-1]
        for step in self.data.maps[-2::-1]:
            base.update(step)
        self.data.clear()
        self.data.maps[0] = base

    @classmethod
    def undoable(cls, func):
        """Decorator - apply on functions and methods that will use Raster functions so that
        they automatically start an undo_group.

        '@FullShape.undoable'
        """
        return cls._inner_undoable(func, _inner_func=False)

    @classmethod
    def _inner_undoable(cls, func, *, _inner_func=True):
        """Undo marker, but for 'final' methods inside the undoable-shape class itself:
        this will finally know the actual instance where undoing is expected,
        and will interact with tokens set-up in the outher function/methods
        (decorated with 'undoable') to actually create the undo-group dictionary to
        be stacked.
        """
        @wraps(func)
        def undo_wrapper(*args, **kwargs):
            class_markers = getattr(cls._undo_registry, "class_markers", None)
            if class_markers is None:
                class_markers = cls._undo_registry.class_markers = {}
            outter_level = False
            if "state" not in class_markers:
                # FIXME: the 'key' here would be a unique 'chain-call-lineage'
                # starting on the outermost undoable function, and that
                # would not be mixed across threads/asyncio_tasks
                # meanwhile, the fixed key "state" will do
                class_markers["state"] = _UNDO_START_MARK
                outter_level = True
            if _inner_func and class_markers["state"] is _UNDO_START_MARK:
                self = args[0]
                # new undo group
                if self.undo_active:
                    self.data.push()
                    class_markers["state"] = _UNDO_IN_PROGRESS_MARK
                    self.verify_and_merge_max_undo_groups()
                # FIXME: maybe think of a non-linear redo strategy?
                self.redo_data.clear()
            try:
                result = func(*args, **kwargs)
            finally:
                if outter_level:
                    del class_markers["state"]
            return result

        return undo_wrapper

    def undo_group_start(self):
        if self.undo_active:
            class_markers = getattr(self.__class__._undo_registry, "class_markers", None)
            class_markers["state"] = _UNDO_START_MARK
            self.verify_and_merge_max_undo_groups()

    def undo_group_end(self):
        class_markers = getattr(self.__class__._undo_registry, "class_markers", None)
        if class_markers.get("state") is not None:
            del class_markers["state"]

    def verify_and_merge_max_undo_groups(self):
        while len(self.data.maps) > self.max_undo_steps + 1:
            # merge the third-to-last and second-to-last groups:
            if self.max_undo_steps >= 2:
                self.data.maps[-2].update(self.data.maps[-3])
                del self.data.maps[-3]
            else:
                self.data.maps[-1].update(self.data.maps[-2])
                del self.data.maps[-2]


class FullShape(RasterUndo, Shape):
    """Shape class carrying all possible data plus kitchen sink

    Args:
      - data: a sequence with 4 planes (sequences), each a sequence with n-rows
            sequences of m-width elements. The first one should carry character
            data: a unicode sequence representing a single glyph. The second
            and 3rd should contain color values, and the 4th an integer
            representing text effects according to Effects values.
    """

    PixelCls = pixel_factory(
        str,
        has_foreground=True,
        has_background=True,
        has_effects=True,
        translate_dots=False,
    )
    _default_bg = EMPTY

    @staticmethod
    def _data_func(size, context=None):
        if context is None:
            import terminedia
            context = terminedia.context
        return [
            [EMPTY * size.x] * size.y,
            [context.foreground] * size.x * size.y,
            [context.background] * size.x * size.y,
            [context.effects] * size.x * size.y,
        ]

    def __init__(self, data, **kw):
        self.width = w = len(data[0][0])
        self.height = h = len(data[0])
        self.rect = Rect((w,h))
        self.load_data(data, (w,h))
        #self.value_data, self.fg_data, self.bg_data, self.eff_data = (
            #self.load_data(plane, (w, h)) for plane in data
        #)
        # self.data is created as a side-effect in load_data
        #del self.data
        super().__init__(**kw)

    def load_data(self, data_planes, size):
        original_undo = getattr(self, "undo_active", False)
        self.undo_active = False
        w, h = size
        self.data = PixelDict()
        data_planes[0] = chain(*data_planes[0])
        iter_data = zip(*data_planes)
        for y in range(h):
            for x in range(w):
                self._raw_setitem((x, y), next(iter_data))
        self.undo_active = original_undo

    def get_raw(self, pos):
        if isinstance(pos, list):
            pos = V2(pos)
        value = self.data.get(pos, None) if pos in self.rect else None

        if value is None:
            value = [EMPTY, self.context.color, self.context.background, self.context.effects]
            self.data[pos] = value
        if self.undo_active:
            # mutations have to be written back, so they are placed in to the chainned undo_group
            value = value[:]
        return value

    def __getitem__(self, pos):
        """Values for each pixel are: character, fg_color, bg_color, effects.
        """
        v = super().__getitem__(pos)
        if v:
            return v

        value = self.get_raw(pos)
        pixel = self.PixelCls(*value)
        if self.context.transformers:
            pixel =  self.context.transformers.process(self, pos, pixel)
        if self.has_sprites:
            pixel = self.sprites.get_at(pos, pixel)
        return pixel

    @RasterUndo._inner_undoable
    def __setitem__(self, pos, value):
        """
        Values set for each pixel are: character - only spaces (0x20) or "non-spaces" are
        taken into account for PalettedShape
        """
        pos = V2(pos)
        self.dirty_mark_pixel(pos)

        force_transparent_ink = getattr(self.context, "force_transparent_ink", False)

        #offset = self.get_data_offset(pos)
        if pos not in self.rect:
            return
        if isinstance(value, Pixel):
            value = value.get_values(self.context, self.PixelCls.capabilities)
        else:
            if isinstance(value, bool):
                value = self.context.char if value else EMPTY
            value = [value] if isinstance(value, str) or value is TRANSPARENT else list(value)
            value += [
                self.context.color,
                self.context.background,
                self.context.effects,
            ][len(value) - 1 :]

        #####################
        # Apply pre-transformers: backed in transformations specified in context.
        #####################

        if self.context.pretransformers:
            value = self.context.pretransformers.process(self, pos, self.PixelCls(*value))

        ############
        # Check final width (after have to apply transformation effect)
        ###########
        offset2 = None

        effects = value[3] if (value[3] != TRANSPARENT or force_transparent_ink) else self.get_raw(pos)[3]
        transform_effects = (effects & UNICODE_EFFECTS) if effects != TRANSPARENT else Effects.none
        # FIXME: check for unicode combining gliphs
        final_char = value[0]
        if isinstance(final_char, (bool, int)):
            final_char = self.context.char if final_char else EMPTY
        if final_char == CONTINUATION:
            if self.get_raw(pos)[0] == CONTINUATION:
                # we are likely being blitted from a source with matching parameters.
                # attributes are already set in this cell from
                # previous character setting
                return

        if final_char not in (TRANSPARENT, CONTINUATION):
            if transform_effects:
                final_char = translate_chars(value[0], transform_effects)
            double_width = char_width(final_char) == 2
            if double_width:
                if not getattr(self.context, "text_rendering_styled", None) == 1:
                    if pos[0] == self.width - 1:  # Right shape edge
                        double_width = False
                    else:
                        offset2 = pos[0] + 1
                else:
                    # a character sequence of styled-text is being rendered.
                    if pos[0] == 0:
                        # FIXME: if a double-width char hits the edge in RTL
                        # printing, this have to be handled in higher level
                        pass
                    if self.context.direction == Directions.LEFT:
                        # EXPERIMENTAL: change actual target in this
                        # situation (rendering_text and going left)
                        # and leave a CONTINUATION marker on the target position.
                        offset2 = pos[0]
                        pos = list(pos)
                        pos[0] -= 1
                    else:
                        if pos[0] == self.width - 1:  # Right shape edge
                            double_width = False
                        offset2 = pos[0] + 1
        else:
            double_width = False
        self.context.shape_lastchar_was_double = double_width
        self._raw_setitem(pos, value, force_transparent_ink, double_width, offset2)

    def _raw_setitem(self, pos, value, force_transparent_ink=False, double_width=False, offset2=None):
        pixel = self.get_raw(pos)
        if offset2:
            pixel2 = self.get_raw((offset2, pos[1]))
        for i, component in enumerate(value):
            # the idea is that "TRANSPARENT" won't affect the corresponding component.
            # but "force_transparent_ink" can set the value of the component itself to
            # be the "transparent" special marker
            if component is not TRANSPARENT or force_transparent_ink:
                pixel[i] = component
                if double_width:
                    pixel2[i] = component if i != 0 else CONTINUATION
        if self.undo_active:
            self.data[pos] = pixel

            if offset2:
                self.data[offset2, pos[1]] = pixel2

    def _resize_data(self, new_size):
        return

    @classmethod
    def promote(cls, other_shape, resolution=None):
        """Makes a FullShape copy of the other shape

        This allows the new shape to be used with Transformers,
        Sprites, and other elements that might not be supported
        in the other shape classes
        """

        if not resolution:
            new_shape = cls.new(other_shape.size)
            draw = new_shape.draw
        else:
            size = size_in_blocks(other_shape.size, resolution)
            new_shape = cls.new(size)
            draw = getattr(new_shape, resolution).draw

        draw.blit((0,0), other_shape)

        return new_shape

class ShalowShapeRepr:
    def __init__(self, original: Shape):
        """The final visible pixel data of a shape as a simple pickleable object

        This can be pickled into disk, and later restored into a new shape.

        Warning: This class applies the visible effects and otherwise ignore text-plane information,
        marks, sprites and any Transformers. A simple Python object is written to disk,
        which can be retrieved.
        """
        self.size = original.size
        self.data = []
        self.cls = original.__class__
        for pos in Rect(self.size).iter_cells():
            self.data.append(tuple(original[pos]))

    def restore(self):
        """Recreates a Shape of the original class with the flattened data"""
        # FIXME: Palleted shapes do not save Palette information
        shape = self.cls.new(self.size)
        for pos, value in zip(Rect(self.size).iter_cells(), self.data):
            shape[pos] = value
        return shape



def shape(data, color_map=None, promote=False, resolution=None, **kwargs):
    """Factory for shape objects

    Args:
      - data (Filepath to image, open file, image data as text or list of strings)
      - color_map (optional mapping): color map to be used for the image - mapping characters to RGB colors.
      - promote (boolean): Whether to force resulting shape to a FullShape (defaults to False)
      - resolution (str): If promote is True, resolution namespace to use on blitting to
            FullShape ("square", "high", "square")
      - **kwargs: parameters passed transparently to the selected shape class

    Based on inferences on the data attribute, selects
    the appropriate Shape subclass to handle the "data" attribute.
    That is:
    given a string without newlines, it is interpreted as a
    filepath, and if PIL is installed, an RGB "ImageShape"
    class is used to read the image data. If text with "\n"
    is passed in, an PalettedShape is used to directly use
    the passed data as pixels.

    Returns an instance of the selected class with the data set.


    """
    if (
        isinstance(data, str)
        and "\n" not in data
        or isinstance(data, Path)
        or hasattr(data, "read")
    ):
        if hasattr(data, "read"):
            name = Path(getattr(data, "name", "stream"))
        else:
            name = Path(data)
        suffix = name.suffix.strip(".").lower()
        if suffix in "pnm ppm pgm".split():
            cls = PGMShape
        elif suffix == "snapshot": # FIXME: find a better way to detect a pickle-file
            import pickle
            obj = pickle.load(open(data, "rb"))
            # FIXME:  the future full shapes may be pickled, and no need to call  "restore" method
            return obj.restore()

        else:
            cls = ImageShape
    elif PILImage and isinstance(data, PILImage.Image):
        cls = ImageShape
    elif isinstance(data, (list, str)):
        cls = PalettedShape
    elif isinstance(data, Shape):
        return data
    elif isinstance(data, tuple) and len(data) == 2:
        return FullShape.new(data, **kwargs)
    else:
        raise NotImplementedError("Could not pick a Shape class for given arguments!")
    result = cls(data, color_map, **kwargs)
    if promote:
        result = FullShape.promote(result, resolution=resolution)
    return result
