import binascii
from copy import copy
from pathlib import Path
import threading

from terminedia.image import Shape, PalettedShape
from terminedia.unicode import split_graphemes
from terminedia.utils import contextkwords, V2, Rect, ObservableProperty
from terminedia.values import Directions, EMPTY, TRANSPARENT

from .fonts import render
from ..text import style

from weakref import WeakKeyDictionary, finalize

class ObservableProperty:
    def __init__(self, fget, fset=None, fdel=None):
        self.fget = fget
        self.fset = fset
        self.fdel = fdel
        self.name = self.fget.__name__
        self.registry = WeakKeyDictionary
        self.callbacks = {}
        self.next_handler_id = 0

    def setter(self, func):
        self.fset = func

    def deleter(self, func):
        self.fdel = func

    def __get__(self, instance, owner):
        if instance is None:
            return self
        value = self.fget(instance)
        if instance in self.registry:
            self.execute(instance, "get", value)
        return value

    def __set__(self, instance, value):
        value = self.fset(instance, value)
        if instance in self.registry:
            self.execute(instance, "set", value)
        return value

    def __delete__(self, instance):
        value = self.fdel(instance)
        if instance in self.registry:
            self.execute(instance, "del")
        return value

    def execute(self, instance, event, value=None):
        for target_event, handler in self.registry.get(instance, ()):
            if target_event == event and callback in self.callbacks:
                callback, args = self.callbacks[handler]
                callback(*args)

    def register(self, instance, event, callback, *args):
        handler = self.next_handler_id
        self.registry.setdefault(instance, []).append(event, handler)
        self.callbacks[handler] = (callback, args)
        def eraser(self, id):
            if id in self.callbacks:
                del self.callbacks[id]
        finalize(instance,  eraser, self, self.handler)
        self.next_handler_id += 1
        return handler

    def unregister(self, handler):
        if handler in self.callbacks:
            del self.callbacks[handler]
            return True
        return False

    def __repr__(self):
        return f"<{self.__class__.__name__} on {self.fget.__qualname__} with {len(self.callbacks)} registered callbacks>"





class CharPlaneData(dict):
    """2D Data structure to hold the text contents of a text plane.

    Indices should be a V2 (or 2 sequence) within width and height ranges
    """

    __slots__ = ("_parent", "_width", "_height", "_size", "_dirty")

    def __new__(cls, parent):
        instance = super().__new__(cls)
        instance._parent = parent
        return instance

    def __init__(self, size):
        pass

    @property
    def width(self):
        if self._dirty:
            self._update_size()
        return self._width

    @property
    def height(self):
        if self._dirty:
            self._update_size()
        return self._height

    @property
    def size(self):
        if self._dirty:
            self._update_size()
        return self_size

    def _update_size(self):
        self._size = self._parent.size
        self._width = self._size[0]
        self._height = self._size[1]

    def __getitem__(self, pos):
        if not (0 <= pos[0] < self.width) or not (0 <= pos[1] < self.height):
            raise IndexError(f"Text position out of range - {self.size}")
        return super().get(pos, EMPTY)

    def __setitem__(self, pos, value):
        if not (0 <= pos[0] < self.width) or not (0 <= pos[1] < self.height):
            raise IndexError(f"Text position out of range - {self.size}")
        super().__setitem__(pos, value)


plane_alias = {
    "block": 8,
    "sextant": 3,
    "high": 4,
    "square": (8, 4),
    "braille": 2,
    "normal": 1,
}

# Shift caused by each 1 unit of padding (always in character-blocks) on
# the pixel resolution each text size uses:
pad_factors = {
    1: (1, 1),
    2: (2, 4),
    3: (2, 3),
    4: (2, 2),
    (8, 4): (1, 2),
    8: (1, 1)
}

# Shift caused in text-content size by each unit of padding:
pad_factors_for_text = {
    1: (1, 1),
    2: (0.25, 0.5),
    3: (0.25, 1/3),
    4: (0.25, 0.25),
    (8, 4): (0.125, 0.25),
    8: (0.125, 0.125)
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
        self.reset_padding()

    def reset_padding(self):
        self.padding = 0
        self.pad_left = self.pad_right = self.pad_top = self.pad_bottom = None

    @property
    def size(self):
        base = V2(self.owner.size)
        fx, fy = pad_factors_for_text[self.current_plane]
        size = base - (
            ((self.padding if self.pad_left is None else self.pad_left) +
            (self.padding if self.pad_right is None else self.pad_right)),
            ((self.padding if self.pad_top is None else self.pad_top) +
            (self.padding if self.pad_bottom is None else self.pad_bottom))
        )

        size = V2(size.x * fx, size.y * fy)
        return size

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
        plane["marks"] = marks = style.MarkMap()
        concretized_text = copy(self)
        concretized_text.current_plane = index
        plane["data"] = data = CharPlaneData(concretized_text)
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
        self._char_at(value, pos)

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
        try:
            self.plane[pos] = char
        except IndexError:
            # Think on storing "lost characters" - but where to put them?
            return
        self.owner.context.last_pos = pos
        self.planes[self.current_plane]["last_pos"] = pos
        self.blit(pos)

    def blit(self, index, target=None, clear=True):
        if target is None:
            target = self.owner

        char = self.plane[index]

        if char is EMPTY and not clear:
            return

        index = V2(index)
        cur_plane = self.current_plane

        if self.padding or self.pad_top or self.pad_left:
            pad_top = self.pad_top if self.pad_top is not None else self.padding
            pad_left = self.pad_left if self.pad_left is not None else self.padding
            index_offset = (
                pad_left * pad_factors[self.current_plane][0],
                pad_top * pad_factors[self.current_plane][1]
            )
        else:
            index_offset = (0, 0)

        if self.current_plane == 1:
            # self.context.shape_lastchar_was_double is set in this operation.
            target[index + index_offset] = char
            return

        rendered_char = render(
            self.plane[index], font=target.context.font or self.font
        )
        index = (index * 8).as_int + index_offset
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
