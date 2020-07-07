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
    "sextant": 3,
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
        self.transformers_map = {}

    @property
    def size(self):
        return self.plane.size

    def _build_plane(self, index, char_width=None):
        char_height = index
        if index == (8, 4):
            char_width = 8
            char_height = 4
        if index == 3:
            char_width = 4
            char_height = 2.5
        if not char_width:
            char_width = char_height
        self.planes[index] = plane = dict()
        if getattr(self, "current_plane", False):
            raise RuntimeError("Concrete instance of text - can't create further planes")
        plane["width"] = width = self.owner.width // char_width
        plane["height"] = height = int(self.owner.height // char_height)
        plane["data"] = data = CharPlaneData((width, height))
        plane["marks"] = marks = style.MarkMap()
        concretized_text = copy(self)
        concretized_text.current_plane = index
        concretized_text.plane = data
        concretized_text.marks = marks
        concretized_text.font = ""
        concretized_text.width = width
        concretized_text.height = height
        concretized_text.ticks = 0
        concretized_text.writtings = []
        concretized_text.writtings_index = set()
        concretized_text._reset_marks()
        plane["text"] = concretized_text

    def _reset_marks(self):
        self.marks.clear()
        self.marks.special.clear()
        self.marks[Rect((self.width, 0, self.width + 1, self.height))] = style.Mark(moveto=(0, style.RETAIN_POS), rmoveto=(0,1))

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
        self._char_at(char, pos)

    @contextkwords(context_path="owner.context", text_attrs=True)
    def at(self, pos, text, transformerlib=None):
        """Renders text at position.

        Args:
          - pos (2-sequence): Coordinates at which to start the text
          - text (str): Text to render. May include special markup
          - transformerlib (Mapping[str:terminedia.Transformer]): updates
                the internal transformers library and become available
                to use from the markup
          - "context-args" (color, background, effects, font, direction):
                context values to be used to render passed text.
        Returns:
            V2: with the last printed position.


        Text is rendered same as using the "="  attribution like in
        screen.text[1][0,0] = "My text" - but this method returns
        the postion of the last character printed, allows
        context attributes to be passed as parameters.

        The Transformers parameter accepts  a "transformers" dictionary
        that will be incorporated into the local "transformers" available
        to be used by name from markup in the text, like in:
        `screen.text[1].at((0,0), "[transformers: upper]My text",
            transformers={"upper": Transformer(char=lambda char: char.upper())}
        )`

        Note that "transformers" set in a call in this call will
        update the internal dictionary for the "text" instance
        associated with a Shape in all resolutions, and remain available
        after the call.

        For fine-grained control of available transformers,
        the `Text.transformers_map` attribute is a plain
        dictionary that can be changed at will.

        """
        if transformerlib:
            self.transformers_map.update(transformerlib)

        return self._at(pos, text)

    def _at(self, pos, text):
        tokens = style.MLTokenizer(text)
        styled = tokens(text_plane=self, starting_point=pos)
        self.render_styled_sequence(styled)
        last_pos = self.planes[self.current_plane]["last_pos"]
        return last_pos

    def _char_at(self, char, pos):
        self.plane[pos] = char
        self.owner.context.last_pos = pos
        self.planes[self.current_plane]["last_pos"] = pos
        self.blit(pos)

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
        elif self.current_plane == 3:
            target.sextant.draw.blit(index, rendered_char, erase=clear)
        elif self.current_plane == 4:
            target.high.draw.blit(index, rendered_char, erase=clear)
        elif self.current_plane == (8, 4):
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

    def update(self):
        """Re-render any writting on the plane that was done using SpecialMarks
        """
        self.ticks += 1
        for writting in self.writtings:
            # if not writting.mark_sequence.get("special") and not self.marks.special:
            #    continue
            self.render_styled_sequence(writting)

    def clear(self):
        self.ticks = 0
        self.writtings[:] = []
        self.writtings_index.clear()
        self.plane.clear()
        self._reset_marks()

    def _render_styled_lock(self, context):
        with self.owner.context(context=context) as ctx, self._render_lock:
            yield self._char_at

    def render_styled_sequence(self, styled):
        """Render an instance of terminedia.text.style.StyledSequence directly

        Usually, will be called automatically by assignments to a position in the text
        plane, but a styled_sequence can be crafted with SpecialMarks in a way
        automatic assignment would not work.

        Also, called internally to update SyledSequences that contain animations.
        """
        if not styled in self.writtings_index:
            self.writtings_index.add(styled)
            self.writtings.append(styled)
        styled.render()

    @contextkwords(context_path="owner.context")
    def print(self, text):
        last_pos = self.planes[self.current_plane]["last_pos"]
        self.at(last_pos + self.owner.context.direction, text)

    def __repr__(self):
        return "".join(
            ["Text [\n", f"owner = {self.owner}\n", f"planes = {self.planes}\n", "]"]
        )
