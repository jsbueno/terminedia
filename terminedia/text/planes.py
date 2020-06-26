import binascii
from copy import copy
from pathlib import Path
import threading

from terminedia.image import Shape, PalettedShape
from terminedia.unicode import split_graphemes
from terminedia.utils import contextkwords, V2, Rect
from terminedia.values import Directions, EMPTY, TRANSPARENT

from .fonts import render
from ..text import style

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


plane_alias = {
    "block": 8,
    "high": 4,
    "square": (8, 4),
    "braille": 2,
    "normal": 1,
}

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

    _render_lock = threading.Lock()

    def __init__(self, owner):
        """Not intented to be instanced directly - instantiated as a Shape property.

        Args:
          - owner (Union[Screen, Shape]): owner instance, target of rendering methods
      """
        self.owner = owner
        self.planes = {}


    def set_ctx(self, key, value):
        return setattr(self.owner.context, f"local_storage_text_{self.current_plane}_{key}", value)

    def get_ctx(self, key, default=None):
        return getattr(self.owner.context, f"local_storage_text_{self.current_plane}_{key}", default)

    @property
    def size(self):
        return self.plane.size

    def _build_plane(self, index, char_width=None):
        char_height = index
        if index == (8, 4):
            char_width = 8
            char_height = 4
        if not char_width:
            char_width = char_height
        self.planes[index] = plane = dict()
        if getattr(self, "current_plane", False):
            raise RuntimeError("Concrete instance of text - can't create further planes")
        plane["width"] = width = self.owner.width // char_width
        plane["height"] = height = self.owner.height // char_height
        plane["data"] = data = CharPlaneData((width, height))
        plane["marks"] = marks = CharPlaneData((width, height))
        concretized_text = copy(self)
        concretized_text.current_plane = index
        concretized_text.plane = data
        concretized_text.marks = marks
        concretized_text.font = ""
        concretized_text.width = width
        concretized_text.height = height
        plane["text"] = concretized_text

    def _checkplane(self, index):
        if not isinstance(index, (int, tuple)):
            raise TypeError(
                "Use an integer or tuple index to retrieve the corresponding character plane for the current target"
            )
        if index not in self.planes:
            self._build_plane(index)
        return self.planes[index]

    def __getitem__(self, index):
        index = plane_alias.get(index, index)
        if "current_plane" not in self.__dict__:
            self._checkplane(index)
            return self.planes[index]["text"]
        return self.plane[index]

    def __setitem__(self, index, value):
        if isinstance(index[0], slice) or isinstance(index[1], slice):
            raise NotImplementedError()
        if len(value) > 1 and len(split_graphemes(value)) > 1:
            self._at(index, value)
            return

        self.plane[index] = value
        self.set_ctx("last_pos", index)
        self.blit(index)

    def blit(self, index, target=None, clear=True):
        if target is None:
            target = self.owner

        char = self.plane[index]

        if char is EMPTY and not clear:
            return

        if self.current_plane == 1:
            # self.context.shape_lastchar_was_double is set in this operation.
            target[index] = char
            return

        rendered_char = render(
            self.plane[index], font=target.context.font or self.font
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
        data = self.plane

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

    def _render_styled(self, context):
        with self.owner.context(context=context) as ctx, self._render_lock:
            yield self._char_at
            self.set_ctx("last_pos", getattr(ctx, "last_pos", (0, 0)))

    def _char_at(self, char, pos):
        self.plane[pos] = char
        self.owner.context.last_pos = pos
        self.blit(pos)

    @contextkwords(context_path="owner.context", text_attrs=True)
    def at(self, pos, text):
        return self._at(pos, text)

    def _at(self, pos, text):
        tokens = style.MLTokenizer(text)
        styled = tokens(text_plane=self, starting_point=pos)
        styled.render()
        return self.get_ctx("last_pos")

    @contextkwords(context_path="owner.context")
    def print(self, text):
        last_pos = self.get_ctx("last_pos", default=(0, 0))
        self.at(last_pos, text)

    def __repr__(self):
        return "".join(
            ["Text [\n", f"owner = {self.owner}\n", f"planes = {self.planes}\n", "]"]
        )
