import binascii
from copy import copy
from pathlib import Path

from terminedia.image import Shape, PalettedShape
from terminedia.utils import contextkwords, V2, Rect
from terminedia.values import Directions, EMPTY, TRANSPARENT

from .fonts import render

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
        return super().get(pos, EMPTY)

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
    1 - for normal text, 2 for text rendered with Braille unicode chars,
    4 for characters rendered with 1/4 block
    characters and 8 for characters rendered by block characters
    as pixels, are implemented with the default fonts.
    (as in `screen.text[4].at((3,4), "hello")` )
    the public methods here issue commands directly to the owner's
    `draw`. `high.draw` and `braille.draw` drawing namespaces - or the owner's values
    for the text[1] plane.
    """

    def __init__(self, owner):
        """Not intented to be instanced directly - instantiated as a Shape property.

        Args:
          - owner (Union[Screen, Shape]): owner instance, target of rendering methods
      """
        self.owner = owner
        self.planes = {}

    @property
    def current_plane(self):
        if not isinstance(self.__dict__.get("current_plane"), (int, tuple)):
            raise TypeError(
                "Please select the character plane with `.text[#]` before using this method"
            )
        return self.__dict__["current_plane"]

    def set_ctx(self, key, value):
        return setattr(self.owner.context, f"local_storage_text_{self.current_plane}_{key}", value)

    def get_ctx(self, key, default=None):
        return getattr(self.owner.context, f"local_storage_text_{self.current_plane}_{key}", default)

    @current_plane.setter
    def current_plane(self, value):
        self.__dict__["current_plane"] = value

    @property
    def plane(self):
        return self.planes[self.current_plane]

    def _build_plane(self, index, char_width=None):
        char_height = index
        if index == (8, 4):
            char_width = 8
            char_height = 4
        if not char_width:
            char_width = char_height
        self.planes[index] = plane = dict()
        plane["width"] = width = self.owner.width // char_width
        plane["height"] = height = self.owner.height // char_height
        plane["data"] = data = CharPlaneData((width, height))
        plane["font"] = ""

    def _checkplane(self, index):
        if not isinstance(index, (int, tuple)):
            raise TypeError(
                "Use an integer or tuple index to retrieve the corresponding character plane for the current target"
            )
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

    def blit(self, index, target=None, clear=True):
        if target is None:
            target = self.owner

        char = self.plane["data"][index]

        if char is EMPTY and not clear:
            return

        if self.current_plane == 1:
            # self.context.shape_lastchar_was_double is set in this operation.
            target[index] = char
            return

        rendered_char = render(
            self.plane["data"][index], font=target.context.font or self.plane["font"]
        )
        index = (V2(index) * 8).as_int
        if self.current_plane == 2:
            target.braille.draw.blit(index, rendered_char, erase=clear)
        elif self.current_plane == 4:
            target.high.draw.blit(index, rendered_char, erase=clear)
        elif self.current_plane == (8,4):
            target.square.draw.blit(index, rendered_char, erase=clear)
        elif self.current_plane == 8:
            target.draw.blit(index, rendered_char, erase=clear)
        else:
            raise ValueError(f"Size {self.current_plane} not implemented for rendering")

    def refresh(self, clear=True, *, preserve_attrs=False, rect=None, target=None):
        """Render entire text buffer to the owner shape

        Args:
          - clear (bool): whether to render empty spaces. Default=True
          - preserve_attrs: whether to keep colors and effects on the rendered cells,
                or replace all attributes with those in the current context
          - rect (Optional[Rect]): area to render. Defaults to whole text plane
          - target (Optional[Shape]): where to render to. Defaults to owner shape.
        """

        if "current_plane" not in self.__dict__:
            raise TypeError("You must select a text plane to render - use .text[<size>].refresh()")

        if target is None:
            target = self.owner
        data = self.plane["data"]

        if not rect:
            rect = Rect((0,0), data.size)
        elif not isinstance(rect, Rect):
            rect = Rect(rect)
        with target.context as context:
            if preserve_attrs:
                context.color = TRANSPARENT
                context.background = TRANSPARENT
                context.effects = TRANSPARENT

            for pos in rect.iter_cells():
                self.blit(pos, target=target, clear=clear)

    @contextkwords(context_path="owner.context", text_attrs=True)
    def at(self, pos, text):
        pos = V2(pos)
        for char in text:
            self[pos] = char
            pos += self.owner.context.direction
            # FIXME: handle char-width guessing standalone here
            # That will enable double width detection for other text planes than 1,
            # and fix ltr case properly.
            if getattr(self.owner.context, "shape_lastchar_was_double", False):
                if 0 < self.owner.context.direction[0] < 2:
                    pos += (1, 0)
                elif -2 < self.owner.context.direction[0] < 0:
                    # FIXME: not perfect, as next char might not be double width.
                    # will handle common case of rtl with double-width chars string, tough.
                    pos -= (1, 0)

        self.set_ctx("last_pos", pos)

    @contextkwords(context_path="owner.context")
    def print(self, text):
        last_pos = self.get_ctx("last_pos", default=(0, 0))
        self.at(last_pos, text)

    def __repr__(self):
        return "".join(
            ["Text [\n", f"owner = {self.owner}\n", f"planes = {self.planes}\n", "]"]
        )
