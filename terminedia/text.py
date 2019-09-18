import binascii
from copy import copy
from pathlib import Path

from terminedia.image import Shape, PalettedShape
from terminedia.utils import V2
from terminedia.values import Directions
try:
    # This is the only Py 3.7+ specific thing in the project
    from importlib import resources
except ImportError:
    resources = None


font_registry = {}

def load_font(font_path, initial=0, last=256, ch1=" ", ch2="#"):

    if font_path == "DEFAULT" and resources:
        data = list(resources.open_text("terminedia.data", "unscii-8.hex"))

    elif font_path == "DEFAULT":
        path = Path(__file__).parent / "data" / "unscii-8.hex"
        data = list(open(path).readlines())

    else:
        data = list(open(font_path).readlines())

    font = {}

    for i, line in enumerate(data[initial:last], initial):
        line = line.split(":")[1].strip()
        line = binascii.unhexlify(line)
        char  = "\n".join(f"{bin(v).split('b')[1]}".zfill(8)  for v in line)
        char = char.replace("0", ch1).replace("1", ch2)
        font [chr(i)] = char

    return font


def render(text, font=None, shape_cls=PalettedShape, direction=Directions.RIGHT):
    if font is None:
        font = "DEFAULT"

    if font not in font_registry:
        font_registry[font] = load_font(font)

    font = font_registry[font]
    phrase = [shape_cls(font[chr]) for chr in text]
    if len(text) == 0:
        return shape_cls.new((0,0))
    elif len(text) == 1:
        return phrase[0]
    return phrase[0].concat(*phrase[1:], direction=direction)


class CharPlaneData(dict):
    """2D Data structure to hold the text contents of a text plane.

    Indices should be a V2 (or 2 sequence) within width and height ranges
    """
    __slots__ = ("_size",)

    def __new__(cls, size):
        instance = super().__new__(cls)
        instance._size = size
        return instance

    def __init__(self, size):
        pass

    @property
    def width(self):
        return self._size[0]

    @property
    def height(self):
        return self._size[1]

    @property
    def size(self):
        return self._size

    def __getitem__(self, pos):
        if not (0 <= pos[0] < self.width) or not (0 <= pos[1] < self.height):
            raise ValueError(f"Text position out of range - {self.size}")
        return super().get(pos, " ")

    def __setitem__(self, pos, value):
        if not (0 <= pos[0] < self.width) or not (0 <= pos[1] < self.height):
            raise ValueError(f"Text position out of range - {self.size}")
        super().__setitem__(pos, value)


class Text:
    """Text handling API

    An instance of this class is attached to :any:`Screen` and :any:`Shape`
    instances as the :any:`text` attribute.
    All context-related information is kept on the associated owner instance.
    ,
    Prior to issuing any text command, one should select a character "plane".
    Planes refer to the number of text blocks used for plotting each character
    on the final rendering target (Shape or Screen). Thus, the values
    1 - for normal text, 4 for Latin characters rendered with 1/4 block
    normal characters and 8 for characters rendered by block characters
    as pixels, are implemented with the default fonts.
    (as in `screen.text[4].at((3,4), "hello")` )
    the public methods here issue commands directly to the owner, or
    to the owner's `draw` and `high.draw` drawing namespaces.
    """

    def __init__(self, owner):
        """Not intented to be instanced directly -

        Args:
          - owner (Union[Screen, Shape]): owner instance, target of rendering methods
      """
        self.owner = owner
        self.planes = {}

    @property
    def current_plane(self):
        if not isinstance(self.__dict__.get("current_plane"), int):
            raise TypeError("Please select the character plane with `.text[#]` before using this method")
        return self.__dict__["current_plane"]

    @current_plane.setter
    def current_plane(self, value):
        self.__dict__["current_plane"] = value

    @property
    def plane(self):
        return self.planes[self.current_plane]

    def _build_plane(self, index, char_width=None):
        char_height = index
        if not char_width:
            char_width = char_height
        self.planes[index] = plane = dict()
        plane["width"] = width = self.owner.width // char_width
        plane["height"] = height = self.owner.height // char_height
        plane["data"] = data = CharPlaneData((width, height))
        plane["font"] = "DEFAULT"

    def _checkplane(self, index):
        if not isinstance(index, int):
            raise TypeError("Use an integer index to retrieve the corresponding character plane for the current target")
        if index not in self.planes:
            self._build_plane(index)
        return self.planes[index]

    def __getitem__(self, index):
        if "current_plane" not in self.__dict__:
            self._checkplane(index)
            selected_text = copy(self)
            selected_text.current_plane = index
            return selected_text
        return self.plane["data"][index]

    def __setitem__(self, index, value):
        if isinstance(index[0], slice) or isinstance(index[1], slice):
            raise NotImplementedError
        self.plane["data"][index] = value
        self.blit(index)

    def blit(self, index, target=None):
        if target is None:
            target = self.owner

        if self.current_plane == 1:
            self.owner[index] = self.plane["data"][index]
        elif self.current_plane == 4:
            char = render(self.plane["data"][index], font=self.plane["font"])
            self.owner.high.draw.blit((index[0] * 8, index[1] * 8), char)
        elif self.current_plane == 8:
            char = render(self.plane["data"][index], font=self.plane["font"])
            self.owner.draw.blit((index[0] * 8, index[1] * 8), char)
        else:
            raise ValueError(f"Size {self.current_plane} not implemented for rendering")

    def at(self, pos, text):
        pos = V2(pos)
        for char in text:
            self[pos] = char
            pos += self.owner.context.direction.value

