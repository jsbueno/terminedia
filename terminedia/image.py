import heapq
import logging
import math
import sys
from abc import ABC, abstractmethod
from collections import namedtuple
from collections.abc import Sequence
from inspect import signature
from io import StringIO
from pathlib import Path
from weakref import ref, ReferenceType

from terminedia.contexts import Context
from terminedia.sprites import SpriteContainer
from terminedia.subpixels import BrailleChars, HalfChars
from terminedia.utils import Color, Rect, V2, LazyBindProperty, char_width, get_current_tick
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
            size_fn=self.get_size,
            context=self.context,
        )

    def _get_highres(self, **kw):
        from terminedia.drawing import HighRes

        return HighRes(self, **kw)

    def _get_text(self):
        from terminedia.text import Text

        return Text(self)

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
        if any("tick" in transformer.signatures for transformer in self.context.transformers):
            self.dirty_set()
            return

        # Collect rects from sprites
        if self.has_sprites:
            for sprite in self.sprites:
                if not sprite.active:
                    continue

                for rect in sprite.dirty_rects:
                    self.dirty_registry.push((tick, sprite.owner_coords(rect), sprite.shape))

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
        if isinstance(output, (str, Path)):
            output = open(
                output, "wt"
            )  # FIXME: for some backends a binary file will be needed.
        if not original_output:
            output = StringIO()

        if backend == "ANSI":
            return self._render_using_screen(output, backend)
        if backend == "HTML":
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
        else:
            raise ValueError(f"Output type {backend!r} not implemented")
        if not original_output:
            return output.get_value()

    def _render_using_screen(self, output, backend):
        from terminedia.screen import Screen

        if output is None:
            file = StringIO()
        else:
            file = output
        sc = Screen(size=V2(self.width, self.height), backend=backend)
        if backend=="ANSI":
            # generate a relocatable image
            sc.commands.__class__.last_pos = V2(0, 0)
            sc.commands.absolute_movement = False
        # Starts recording all image operations on the internal journal
        sc.commands.__enter__()
        sc.blit((0, 0), self)
        # Ends journal-recording, but without calling __exit__
        # which does not allow passing an external file.
        sc.commands.stop_journal()
        # Renders all graphic ops as ANSI sequences + unicode into file:
        sc.commands.replay(output)

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



# "Virtualsubclassing" - 2 days after I wrote there were no
# practical uses for it.
# With it, "ShapeView" can have "__slots__"
@Shape.register
class ShapeView(ShapeApiMixin):
    __slots__ = ("roi", "original", "_draw", "_high", "_text")

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

    Important: on instantating  these shapes, Terminedia will
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

    def load_data(self, file_or_path, size=None):
        """Will load data from an image file using PIL,

        Image is re-scaled to self.size if that is not None.
        """
        if isinstance(file_or_path, PILImage.Image):
            img = file_or_path
        else:
            img = PILImage.open(file_or_path)
        if size is not None:
            pixel_ratio = 1
            size = V2(size) - (1, 1)
            img_size = V2(img.width, img.height)
            if size.x < img_size.x or size.y < img_size.y:
                ratio_x = size.x / img_size.x
                ratio_y = (size.y / img_size.y) * pixel_ratio
                if ratio_x > ratio_y:
                    size = V2(
                        size.x, min((img_size.y * ratio_x / pixel_ratio), size.y - 1)
                    )
                else:
                    size = V2(img_size * ratio_y, size.y / pixel_ratio)

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
        self.data[pos[1] * self.width + pos[0]] = type_(value)


class FullShape(Shape):
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

    @staticmethod
    def _data_func(size):
        return [
            [EMPTY * size.x] * size.y,
            [DEFAULT_FG] * size.x * size.y,
            [DEFAULT_BG] * size.x * size.y,
            [Effects.none] * size.x * size.y,
        ]

    def __init__(self, data):
        self.width = w = len(data[0][0])
        self.height = h = len(data[0])
        self.value_data, self.fg_data, self.bg_data, self.eff_data = (
            self.load_data(plane, (w, h)) for plane in data
        )
        # self.data is created as a side-effect in load_data
        del self.data
        super().__init__()

    def get_raw(self, pos):
        offset = self.get_data_offset(pos)
        if offset is None:
            return (EMPTY, self.context.color, self.context.background, Effects.none)
        return (
            self.value_data[offset],
            self.fg_data[offset],
            self.bg_data[offset],
            self.eff_data[offset],
        )

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

    def __setitem__(self, pos, value):
        """
        Values set for each pixel are: character - only spaces (0x20) or "non-spaces" are
        taken into account for PalettedShape
        """
        pos = V2(pos)
        self.dirty_mark_pixel(pos)

        force_transparent_ink = getattr(self.context, "force_transparent_ink", False)

        offset = self.get_data_offset(pos)
        if offset is None:
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

        ############
        # Check final width (have to apply transformation effect)
        ###########
        effects = value[3] if (value[3] != TRANSPARENT or force_transparent_ink) else self.eff_data[offset]
        transform_effects = (effects & UNICODE_EFFECTS) if effects != TRANSPARENT else Effects.none
        final_char = value[0]
        if isinstance(final_char, bool):
            final_char = self.context.char if final_char else EMPTY
        if final_char == CONTINUATION:
            if self.value_data[offset] == CONTINUATION:
                # we are likely being blitted from a source with matching parameters.
                # attributes are already set in this cell from
                # previous character setting
                return

        if final_char not in (TRANSPARENT, CONTINUATION):
            if transform_effects:
                final_char = translate_chars(value[0], transform_effects)
            double_width = char_width(final_char) == 2
            if double_width:
                if pos[0] == self.width - 1:  # Right shape edge
                    width = 1
                    double_width = False
                else:
                    offset2 = offset + 1
        else:
            double_width = False
        # /check width
        for component, plane in zip(
            value, (self.value_data, self.fg_data, self.bg_data, self.eff_data)
        ):
            if component is not TRANSPARENT or force_transparent_ink:
                plane[offset] = component
            if double_width:
                plane[offset2] = (
                    component if plane is not self.value_data else CONTINUATION
                )
        # set information so higher level users can partake char width (text, blit)
        self.context.shape_lastchar_was_double = double_width

    @classmethod
    def promote(cls, other_shape):
        """Makes a FullShape copy of the other shape

        This allows the new shape to be used with Transformers,
        Sprites, and other elements that might not be supported
        in the other shape classes
        """
        new_shape = cls.new(other_shape.size)
        new_shape.draw.blit((0,0), other_shape)
        return new_shape


def shape(data, color_map=None, **kwargs):
    """Factory for shape objects

    Args:
      - data (Filepath to image, open file, image data as text or list of strings)
      - color_map (optional mapping): color map to be used for the image - mapping characters to RGB colors.
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
        if not PILImage or name.suffix.strip(".").lower() in "pnm ppm pgm":
            cls = PGMShape
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
    return cls(data, color_map, **kwargs)
