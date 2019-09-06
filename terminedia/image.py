import sys
import threading
from collections import namedtuple
from inspect import signature
from pathlib import Path

from terminedia.drawing import Drawing
from terminedia.utils import V2
from terminedia.values import DEFAULT_FG, DEFAULT_BG, Directions


try:
    from PIL import Image as PILImage
except ImportError:
    PILImage = None


PixelClasses = {}
pixel_capabilities = namedtuple("pixel_capabilities", "value_type has_foreground has_background has_text_attributes")


def pixel_factory(value_type=str, has_foreground=True, has_background=False, has_text_effects=False):
    """Returns a custom pixel class with specified capabilities

    Args:
        value_type(str or bool): Data type returned by the pixel
        has_foreground (bool): Whether pixel has a foreground color
        has_background (bool): Whether pixel has a background color
        has_text_effects (bool): Whether pixel has text-attribute flags

    Created pixel classes or instances are not intended to be directly manipulated -
    instead, they are just a way to convey information from internal images/shapes
    to methods that will draw then.
    """

    capabilities = pixel_capabilities(value_type, has_foreground, has_background, has_text_effects)
    if capabilities in PixelClasses:
        Pixel = PixelClasses[capabilities]
    else:
        pixel_tuple = namedtuple(
            "PixelBase",
            (
                ("value",) +
                (("foreground", ) if has_foreground else ()) +
                (("background", ) if has_background else ()) +
                (("text_effects", ) if has_text_effects else ())
            ),
        )

        def __repr__(self):
            return "Pixel({})".format(", ".join(
                f"{field}={getattr(self, field)}" for field in pixel_tuple._fields
            ))

        Pixel = type(
            "Pixel",
            (pixel_tuple,),
            {
                "capabilities": capabilities,
                "__repr__": __repr__,
                "__slots__": (),
            }
        )

        @property
        def value(self):
            value = super(Pixel, self).value
            return (value not in (" .")) if value_type is bool and isinstance(value, str) else value_type(value)

        Pixel.value = value

        PixelClasses[capabilities] = Pixel

    return Pixel


class Shape:
    """'Shape' is intended to represent blocks of colors/backgrounds and characters
    to be applied in a rectangular area of the terminal. In this sense, it is
    more complicated than an "Image" that just care about a foreground color
    and alpha value for each pixel position.

    This is going to be implemented gradually - the first use case
    is a plain old "image" - the capability of including specific characters
    instead of blocks of solid color should be available later as
    subclasses of Shape.

    """

    # this data is to be found into the PixelCls.capabilities

    # foreground = False
    # background = False
    # arbitrary_chars = False
    # character_properties = False  # FUTURE: support for bold, blink, underline...

    PixelCls = pixel_factory(bool)

    def __init__(self, data, color_map=None):
        raise NotImplementedError("This is meant as an abstract Shape class")

    @property
    def context(self):
        if not "context" in self.__dict__:
            context = self.__dict__["context"] = threading.local()
            context.color = DEFAULT_FG
            context.background = DEFAULT_BG
            context.direction = Directions.RIGHT

        return self.__dict__["context"]

    @property
    def draw(self):
        if not "draw" in self.__dict__:
            self.__dict__["draw"] = self._get_drawing_func()

        return self.__dict__["draw"]

    _data_func = staticmethod(lambda size: [" " * size.x] * size.y)
    _get_drawing_func = lambda self: Drawing(
        set_fn = lambda pos: self.__setitem__(pos, self.context.color),
        reset_fn = lambda pos: self.__setitem__(pos, self.context.background),
        size_fn = lambda : V2(self.width, self.height),
        context = self.context
    )

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

    def get_raw(self, pos):
        return self.data[pos[1] * self.width + pos[0]]

    def __getitem__(self, pos):
        """Values for each pixel are: character, fg_color, bg_color, text_attributes.
        """
        raise NotImplementedError("This is meant as an abstract Shape class")

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
        for x in range(self.width):
            for y in range(self.height):
                pos = V2(x, y)
                yield (pos, self[pos])


class ValueShape(Shape):

    PixelCls = pixel_factory(bool, has_foreground=True)

    _data_func = staticmethod(lambda size, color=(0,0,0): [color] * size.x * size.y)
    _allowed_types = (Path, str)

    def __init__(self, data, color_map=None, **kwargs):

        self.kwargs = kwargs
        # TODO: make color_map work as a to-pixel pallete infornmation
        # to L or I images - not only providing a color palette,
        # but also enabbling an "palette color to character" mapping.
        self.color_map = color_map
        if isinstance(data, self._allowed_types) or hasattr(data, "read"):
            self.load_file(data)
            return
        raise NotImplementedError(f"Can't load shape from {type(data).__name__}")

    def load_file(self, file_or_path):
        raise NotImplementedError()

    def __getitem__(self, pos):
        """Composes a Pixel object for the given coordinates.
        """
        color = self.get_raw(pos)

        return self.PixelCls(True, color)

    def __setitem__(self, pos, value):
        """
        Values set for each pixel are 3-sequences with an RGB color value
        """
        self.data[pos[1] * self.width + pos[0]] = value


class PGMShape(ValueShape):

    PixelCls = pixel_factory(bool, has_foreground=True)

    def load_file(self, file_or_path):
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
            line = data[offset: line_end + 1]
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
            raise NotImplementedError(f"File not supported. PNM with magic number: {type_.decode!r}")

        data = data[offset:]
        if ascii:
            data = [int(v) for v in data.split()]
        if len(data) != size.x * size.y * values_per_pixel:
            sys.stderr.write("Warning: malformed PNM file. Trying to continue anyway\n")

        data = [value / max_value for value in data]
        if values_per_pixel == 1:
            data = [(value, value, value) for value in data]
        else:
            data = [tuple(data[i: i + 3]) for i in range(0, len(data), 3)]
        self.data = data


class ImageShape(ValueShape):

    PixelCls = pixel_factory(bool, has_foreground=True)

    _data_func = staticmethod(lambda size, mode="RGB", color=(0, 0, 0): PILImage.new(mode, size, color=color))
    if PILImage:
        _allowed_types = (str, Path, PILImage.Image)

    def load_file(self, file_or_path):
        if isinstance(file_or_path, PILImage.Image):
            img = file_or_path
        else:
            img = PILImage.open(file_or_path)
        if self.kwargs.get("auto_scale", True):
            scr = self.kwargs.get("screen", None)
            pixel_ratio = self.kwargs.get("pixel_ratio", 2)

            size = V2(scr.get_size() if scr else (80, 12))
            img_size = V2(img.width, img.height)
            if size.x < img_size.x or size.y < img_size.y:
                ratio_x = size.x / img_size.x
                ratio_y = (size.y / img_size.y) * pixel_ratio
                if ratio_x > ratio_y:
                    size = V2(size.x, img_size.y * ratio_x / pixel_ratio)
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

    def __setitem__(self, pos, value):
        """
        Values set for each pixel are treated by PIL.
        """
        self.data.putpixel(pos, value)


class PalletedShape(Shape):
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
    text_effects = False  # FUTURE: support for bold, blink, underline...

    PixelCls = pixel_factory(bool, has_foreground=True)

    def __init__(self, data, color_map=None):
        if isinstance(data, (str, list)):
            self.load_paletted(data, color_map)
            return
        elif isinstance(data, Path) or hasattr(data, "read"):
            self.load_file(data)
            return
        raise NotImplementedError(f"Can't load shape from {type(data).__name__}")

    def load_paletted(self, data, color_map):
        if isinstance(data, str):
            data = data.split("\n")
        self.width = max(len(line) for line in data)
        self.height = len(data)
        self.color_map = color_map
        if color_map is None:
            self.PixelCls = pixel_factory(bool, has_foreground=False)
        self.data = [" "] * self.width * self.height

        for y, line in enumerate(data):
            for x in range(self.width):
                char = line[x] if x < len(line) else " "
                # For string-based shapes, '.' is considered
                # as whitespace - this allows multiline
                # strings defining shapes that otherwise would
                # be distorted by program editor trailing space removal.
                if char == ".":
                    char = " "
                self[x, y] = char

    def get_raw(self, pos):
        return self.data[pos[1] * self.width + pos[0]]

    def __getitem__(self, pos):
        """Values for each pixel are: character, fg_color, bg_color, text_attributes.
        """
        char = self.get_raw(pos)
        if self.color_map:
            foreground_arg = (self.color_map.get(char, DEFAULT_FG),)
        else:
            foreground_arg = ()

        return self.PixelCls(char, *foreground_arg)

    def __setitem__(self, pos, value):
        """
        Values set for each pixel are: character - only spaces (0x20) or "non-spaces" are
        taken into account for PalletedShape
        """
        self.data[pos[1] * self.width + pos[0]] = value


def shape(data, color_map=None, **kwargs):
    """Factory for shape objects

    Args:
      - data (Filepath to image, open file, image data as text or list of strings)
      - color_map (optional mapping): color map to be used for the image - mapping characters to RGB colors.
      - **kwargs: parameters passed transparently to the selected shape class

    Based on inferences on the data attribute, selects
    the appropriate Shape subclass to handle the "data" attribute
    as a pattern to be blitted on Screen instances. That is:
    given a string without newlines, it is interpreted as a
    filepath, and if PIL is installd, an RGB "ImageShape"
    class is used to read the image data. If text with "\n"
    is passed in, an PalletedShape is used to directly use
    the passed data as pixels.

    Returns an instance of the selected class with the data set.


    """
    if isinstance(data, str) and "\n" not in data or isinstance(data, Path) or hasattr(data, "read"):
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
        cls = PalletedShape
    elif isinstance(data, Shape):
        return data
    else:
        raise NotImplementedError("Could not pick a Shape class for given arguments!")
    return cls(data, color_map, **kwargs)
