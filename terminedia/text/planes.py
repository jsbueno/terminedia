import binascii
from collections import namedtuple
from copy import copy
from pathlib import Path
import threading

from terminedia.image import Shape, PalettedShape, shape
from terminedia.unicode import split_graphemes
from terminedia.utils import contextkwords, V2, Rect, ObservableProperty, get_current_tick
from terminedia.values import Directions, EMPTY, TRANSPARENT, RETAIN_POS
from terminedia.values import WIDTH_INDEX, HEIGHT_INDEX

from .fonts import render
from ..text import style


class CharPlaneData(dict):
    """2D Data structure to hold the text contents of a text plane.

    Indices should be a V2 (or 2 sequence) within width and height ranges
    """

    __slots__ = ("_parent", "width", "height", "size", "active", "_dirty")

    def __new__(cls, parent):
        instance = super().__new__(cls)
        instance._parent = parent
        return instance

    def __init__(self, size):
        self.active = True

    def _update_size(self, *args):
        size = self.size = self._parent.size
        self.width = size[0]
        self.height = size[1]

    def __getitem__(self, pos):
        for retry in 0, 1:
            if not (0 <= pos[0] < self.width) or not (0 <= pos[1] < self.height):
                if retry == 0:
                    self._update_size()
                    continue
                raise IndexError(f"Text position out of range - {self.size}")
        return super().get(pos, EMPTY)

    def __setitem__(self, pos, value):
        for retry in 0, 1:
            if not (0 <= pos[0] < self.width) or not (0 <= pos[1] < self.height):
                if retry == 0:
                    self._update_size()
                    continue
                raise IndexError(f"Text position out of range - {self.size}")
        if not self.active:
            return
        super().__setitem__(pos, value)


plane_alias = {
    "block": 8,
    "sextant": 3,
    "high": 4,
    "square": (8, 4),
    "braille": 2,
    "normal": 1,
}


plane_names = {**plane_alias, **{value:value for value in plane_alias.values()}}


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
relative_char_size = {
    1: (1, 1),
    2: (0.25, 0.5),
    3: (0.25, 1/3),
    4: (0.25, 0.25),
    (8, 4): (0.125, 0.25),
    8: (0.125, 0.125)
}

_bordersentinel = object()

class Layouts:
    @staticmethod
    def normal(text_plane):
        mark_forward = style.Mark(moveto=(0, RETAIN_POS), rmoveto=(0,1))
        mark_backward = style.Mark(moveto=(WIDTH_INDEX - 1, style.RETAIN_POS), rmoveto=(0,-1))
        for y in range(0, int(text_plane.height)):
            # This is the point where the 'RelativeMarkIndex' was supposed to be needed.
            text_plane.marks[None, y] = mark_forward
            # Writting directly to marks.data instead of marks is the way
            # for MarkMap not to convert a negative index (-1) to a relative index
            # counting from the width of the plane (i.e., it is a "hard" -1)
            text_plane.marks.data[-1, y] = mark_backward
        # self.marks[Rect((self.width, 0, self.width + 1, self.height))] = style.Mark(moveto=(0, style.RETAIN_POS), rmoveto=(0,1))


class _RecordingControl:
    """Simple class to keep track of where each character was printed in an
    output burst.

    A single instance of it is attached at a text_plane, and by using
    text_plane.recording.__enter__ , all printed characters are
    appended to a list, in the form of a (char, pos, tick, (ctx.fg, ctx.bg, ctx.effects)) tuple per char.
    on __exit__ recording stops. A new recording list is returned by __enter__
    each time its called, and results of the last-recording are available
    as self.data.

    This is used internally by widgets so they can track where rendered characters
    are in order to position the cursor.
    """

    def __init__(self, parent):
        self.active = False
        self.data = []

    def __bool__(self):
        return self.active

    def __enter__(self):
        self.data = []
        self.active = True
        return self.data

    def __exit__(self, *args):
        self.active = False

    def register(self, char, pos, tick, ctx_data):
        self.data.append(RenderData(char, pos, tick, ctx_data))

RenderData = namedtuple("RenderData", "char pos tick ctx")
CtxData = namedtuple("CtxData", "foreground background effects")

class TextPlane:
    """Text handling API

    An instance of this class is attached to :any:`Screen` and :any:`Shape`
    instances as the :any:`text` attribute.
    All context-related information is kept on the associated owner instance.
    ,
    Prior to issuing any text command, one should select a character "plane".
    Planes refer to the number of text blocks used for plotting each character
    on the final rendering target (Shape or Screen). Thus, the values
    1 - for normal text, 2 for text rendered with Braille unicode chars,
    4 for characters rendered with 1/4 block, 3 for values rendered with the Unicode 13.0 sextant chars,

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
        self._render_lock = threading.Lock()
        self.owner = owner
        self.planes = {"root": self}
        self.transformers_map = {}
        self.reset_padding()
        self.lock = threading.RLock()  # This is shared across all text-planes for the same owner

    def reset_padding(self):
        self.padding = 0
        self.pad_left = self.pad_right = self.pad_top = self.pad_bottom = None

    padding = ObservableProperty()
    for pad_name in "pad_left pad_right pad_top pad_bottom".split():
        locals()[pad_name] = ObservableProperty(
            lambda s, pad_name=pad_name: s.__dict__.get(name) if s.__dict__.get(pad_name) is not None else s.padding,
            lambda s, v, pad_name=pad_name: s.__dict__.__setitem__(pad_name, v)
        )
    #pad_right = ObservableProperty()
    #pad_top = ObservableProperty()
    #pad_bottom = ObservableProperty()

    @property
    def size(self):
        current_plane = getattr(self, "current_plane", 1)
        base = V2(self.owner.size)
        fx, fy = relative_char_size[current_plane]
        size = base - (
            self.pad_left + self.pad_right,
            self.pad_top + self.pad_bottom
        )
        size = (size * (fx, fy)).as_int
        return size

    @property
    def width(self):
        return self.size[0]

    @property
    def height(self):
        return self.size[1]

    def pos_to_text_cell(self, pos):
        """Given a 1-block coordinate on screen, return the cordinate of the matchng text cell
        on the current plane, taking in account padding.
        """
        if not self.current_plane:
            return pos
        return ((V2(pos) - (self.pad_left, self.pad_top)) / self.char_size).as_int

    def _build_plane(self, index, char_width=None):
        """Internally called to build concrete views, with different resolutions, of a text_plane by the same owner.

        Each shape (or screen) object that features a ".text" attribute pointing to an
        instance o TextPlane, points to an "AbstractRoot" that can't actually render text.
        (Padding and frames can be defined on this root). When an index of
        the text plane like .text[1] or .text[4] is called, another instance of TextPlane,
        sharing some attributes from the parent, is created and added to
        the ".planes" dictionary. These concrete views distinguish thmselves
        due to having the ".current_plane" attribute set.
        """
        char_height = index
        if index == (8, 4):
            char_width = 8
            char_height = 4
        if index == 3:
            char_width = 4
            char_height = 2.5
        if not char_width:
            char_width = char_height
        concretized_text = copy(self)
        self.planes[index] = concretized_text
        # plane = dict()
        if getattr(self, "current_plane", False):
            raise RuntimeError("Concrete instance of text - can't create further planes")
        # plane["width"] = width = self.owner.width // char_width
        # plane["height"] = height = int(self.owner.height // char_height)
        concretized_text.current_plane = index
        concretized_text.char_size = V2(char_width, char_height)
        marks = style.MarkMap(parent=concretized_text)
        # plane["marks"] = marks = style.MarkMap(parent=concretized_text)
        data = CharPlaneData(concretized_text)
        # plane["data"] = data
        concretized_text.plane = data
        concretized_text.marks = marks
        concretized_text.font = ""
        concretized_text.ticks = 0
        concretized_text.writtings = {}
        concretized_text.reset_marks()
        concretized_text.last_pos = None
        concretized_text.recording = _RecordingControl(concretized_text)
        for pad_attr in "padding pad_left pad_right pad_top pad_bottom".split():
            descriptor = getattr(type(self), pad_attr)
            descriptor.register(self, "set", lambda inst, v, attr=pad_attr: setattr(concretized_text, attr, v))
            descriptor.register(concretized_text, "set", data._update_size)
        data._update_size()
        # plane["text"] = concretized_text

    def reset_marks(self, layout=None):
        """Clear all custom positional marks in the text plane
        (attribute .marks) - and, applies the specified text-flow
        layout.
        The layout is a callback, which should take the text-plane
        as sole parameter - it can then fill in Mark objects
        (usually containing "moveto" and "rmoveto" tags) in specific positions
        so that text will flow in the desired directions when reaching the mark
        (the default "normal" layout places marks so that
        at the end of a line the text flows in to the
        beggining (absoulte move) of the next (relative move)
        text line.

        The "Layouts" class in this module is meant
        to be a namespace for a library with popular layouts.
        """
        self.marks.clear()
        self.marks.special.clear()
        if layout is None:
            layout = Layouts.normal
        layout(self)

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
            return self.planes[index]
        return self.plane[index]

    def __setitem__(self, index, value):
        if isinstance(index[0], slice) or isinstance(index[1], slice):
            raise NotImplementedError()
        self.at(index, value)

    # TODO: mark this as 'undoable'.
    # in addition to "raster undo", we also need to remove
    # the 'writtings' entry . could be done by adding a callback
    # to the current raster-undo mechanism.
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

        Note that "transformers" set in a call to this will
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

    @contextkwords(context_path="owner.context", text_attrs=True)
    def extents(self, pos, text, final_pos=True):
        """Return the last position where text would be printed -

        This is a "dry-run" call, equivalent to ".at" but doesn't
        render anything in owner. It won't take a 'transformerslib'
        parameter - if the text that needs to be measured will
        need special transformers set in this TextPlane, they
        should be created beforehand, either with an emptu call
        to `.at` or by updating the `.transformers_lib` dictionary
        directly.


        Args:
          - pos (2-sequence): Coordinates at which to start the text
          - text (str): Text to render. May include special markup
          - final_pos (bool): return position is the positin for the next insertion,
                not of the last character inserted. (default: True)
          - "context-args" (color, background, effects, font, direction):
                context values to be used to render passed text.
        Returns:
            V2: with the last printed position.

        """
        if final_pos:
            text += "a"
        with self.lock:
            try:
                original_last_pos = self.last_pos
                self.owner._raw_setitem = lambda self, *args, **kw: None
                original_writtings = self.writtings
                self.writtings = {}
                self.plane.active = False
                last_pos = self._at(pos, text)
            finally:
                # restore method defined in the shape class:
                self.writtings = original_writtings
                self.last_pos = original_last_pos
                self.plane.active = True
                del self.owner._raw_setitem
        return last_pos


    def _at(self, pos, text):
        with self.lock:
            tokens = style.MLTokenizer(text)
            styled = tokens(text_plane=self, starting_point=pos)
            self.render_styled_sequence(styled)
            return self.last_pos

    def _char_at(self, char, pos):
        try:
            self.plane[pos] = char
        except IndexError:
            # Think on storing "lost characters" - but where to put them?
            return
        ctx = self.owner.context
        direction = ctx.direction
        self.blit(pos)
        if self.recording:
            self.recording.register(char, pos, get_current_tick(), CtxData(ctx.foreground, ctx.background, ctx.effects))

        pos += (int(getattr(ctx, "text_lastchar_was_double", 0)) * direction[0], 0)
        self.owner.context.last_pos = pos
        self.last_pos = pos

    def clear_recording(self):
        """Clear recording of where each character was printed"""
        self._pos_recording.clear()

    def start_recording(self):
        self.clear_recording()
        self.recording = True

    def blit(self, index, target=None, clear=True):
        """Actual function that renders given character to
        the selected backend. Reserved for internal use,
        but could be called by lower level code, explicitly
        rendering a character at another target.
        """
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
            target.context.text_lastchar_was_double = target.context.shape_lastchar_was_double
            return

        # FIXME: take in account double-width chars when rendering
        # big-text
        target.context.text_last_char_was_double = False
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

    def clear(self, layout=None):
        self.ticks = 0
        self.writtings.clear()
        self.plane.clear()
        self.reset_marks(layout=layout)

    def _render_styled_lock(self, context):
        with self.owner.context(context=context) as ctx, self._render_lock:
            yield self._char_at

    def render_styled_sequence(self, styled):
        """Render an instance of terminedia.text.style.StyledSequence directly

        Usually, will be called automatically by assignments to a position in the text
        plane or by the ".at()" method, but a styled_sequence can be crafted with
        SpecialMarks in a way automatic assignment would not work.

        Also, called internally to update StyledSequences that contain animations.
        """
        if not styled in self.writtings:
            # We need just the keys and the order
            # (a dict gives this for free - otherwise we need a set + a sequence)
            self.writtings[styled] = None
        try:
            self.owner.context.text_rendering_styled = self.current_plane
            styled.render()
            self.last_rendered_writing = styled
        finally:

            self.owner.context.text_rendering_styled = None

    def _clear_owner(self):
        # clear the inner contents of the owner when reflowing text, respecting padding
        size = self.size

        corner1 = V2(self.pad_left, self.pad_top)
        corner2 = corner1 + size

        self.owner[corner1.x: corner2.x, corner1.y: corner2.y].draw.fill(char=" ")

    def add_border(self, transform=None, context=None):
        """Adds a text-frame. Increases padding and updates the content.

        The parameter passed should be a transformer - and is primarily
        thought to be one of terminedia.transformers.library.box_transforms.*
        or another one that will use nice unicode line characters for the borders.
        Without a Transformer, a block-char is used for the borders.

        Any transformer can be used, though - the frame is them rendered
        as a solid block-outline

        if `context` is given: uses given context to render the border, otherwise
        the context for the owner shape is used.
        """

        for plane_name, text_plane in self.planes.items():
            if plane_name == "root":
                continue
            text_plane.plane.clear()
        self._clear_owner()

        if all(self.padding == other_pad for other_pad in (self.pad_left, self.pad_right, self.pad_top, self.pad_bottom)):
            self.padding += 1
        else:
            self.pad_left += 1
            self.pad_right += 1
            self.pad_top += 1
            self.pad_bottom += 1

        self.draw_border(transform, context)

        # Refresh all text content;
        for plane_name, concrete_plane in self.planes.items():
            if plane_name == "root":
                continue
            concrete_plane.update()

    def draw_border(self, transform=_bordersentinel, context=None, pad_level=1):
        """Draws an existing border, without changing the shape pattern
        call this just to redraw the border; A new border should be created by
        calling "add_border"
        """
        if transform is _bordersentinel:
            transform = getattr(self, "_last_border_transform", None)
        elif transform != None:
            self._last_border_transform = transform

        size = (self.size * self.char_size) + (1, 1) * pad_level * 2 + (1, 1)

        border_shape = shape(size)

        if context:
            border_shape.context = context
        else:
            border_shape.context = self.owner.context

        with border_shape.context as context:
            border_shape.draw.rect((0, 0), (size))
            if transform:
                context.transformers.append(transform)
            self.owner.draw.blit(V2(self.pad_left, self.pad_top) - (pad_level, pad_level), border_shape)


    @contextkwords(context_path="owner.context")
    def print(self, text):
        last_pos = self.last_pos
        next_pos = (last_pos + self.owner.context.direction) if last_pos is not None else last_pos
        self.at(next_pos, text)

    def __repr__(self):
        if not getattr(self, "current_plane", False):
            return "\n".join(
                ["TextPlane [", f"owner = {self.owner}", f"planes = {self.planes}", "]"]
            )
        return "\n".join(
            [
                f"TextPlane[{self.current_plane}] [",
                f"size = {self.size}",
                f"writtings = {len(self.writtings)}",
                f"padding = {self.padding}",
                f"last_pos = {getattr(self, 'last_pos', '(0, 0)')}",
                f"marks = {self.marks}",
                "]"
            ])
