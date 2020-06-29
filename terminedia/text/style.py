"""Tokenizer and tree-structure for style-applying in text.

Allows one to encode in a single string style changes
instead of having to chunk pieces of text
to change the context for color, effects and transform changes


Also, [future] enable the parsing of more than one
markup style - for example, allowing terminedia
to extract color and movement information from
ANSI text streams generated by other apps.


TMMarkup example:


here comes some text [color:blue] with apples [background:red] infinite [/color /background effect:blink]in joy and blink[/effect]
[direction:up]happy[effect:bold]new year[/effect][direction:left]there we go[/direction]up again[direction: right] the end.

Markup description:
    any text outside of a [...] block is treated as plain text
    double use of square brackets - [[...]] escape on single bracket pair(wip)
    the tag name inside squares can be any of:
        - "color": sets the text foreground color. The color can be spelled as
            a CSS color name ('red', 'yellow', etc...) or using a numeric notation
            with a numeric triplet inside parenthesis (this will be parsed as if
            it were a Pythn tuple. Besides that the special color names "transparent" and
            "default" can also be used. The first ignores color and uses the correspondent
            color already set in the underlying character cell.
        - "foreground": the same as "color"
        - "background": Sets the text foreground color
        - "effect": any effect name from those listed in the "terminedia.effects" enum.
            more than one effect can be activated in the same markup - separate the
            effect names with a "|". Example: "[effect: blink|underline]".
            Some of th provided effects rely on terminal capabilities, such as underline,
            while others depend on an actual character replacing for unicode characters
            providing the visual effect named. The later are not meant to be cumullative,
            as characters can only be replaced once; ex.: "[effect: encircled]". Besides
            all existing effets, the special value "transparent" is also affected, and should
            preserve the effects active in the cell the character will be rendered to.
        - "effects": an alias for "effect"
        - "font" - the font to be used to render the text. Only works for multi-block sized text,
                and for the embedded UNSCII fonts: "fantasy","mcr" and "thin". Ex:
                "[font; thin]", "[font]"
        - "char": replaces all characters inside this tag with the givern one.
        - "direction": One of the 4 directions for text flow: up, down, right and left
            instead of "[direction: left]" , the direction names can be used as tag names.,
            so these are valid: "[left]abcd[up]efgh[right]ijklm"
        - "transformers": one of the Transformer instances listed in "terminedia.transformers.library" (wip)
        - tag name starting with an "/": pops the last corresponding tag and drops its modifications to
        the text flow. ex. "[/color]" (wip)
        - Two comma separated numbers: "teleports" the text the text for that coordinate in
               - the target rendering area. ex. "Hello[5, 3]World", prints 'world" at the 5,3 coordinates.
               - Using the "+" and "-" characers as a numeric prefix will use those numbrs as relative positions
               ex.: "[0, +1]" will move the beginning of text the next line.

        If tags are not closed, styles are not "popped", but this is no problem (no memory laks or such)
        the closing styles feature  is just a matter of convenience to return to previous values
        of the same attribute. Also,
        unlike XML, there is no problem crossing tags; This is valid input:
        "[color: blue] hello [background: #ddd] world [/color] for you [/background]!!"



"""
from __future__ import annotations

from collections.abc import Sequence, MutableMapping
from copy import copy
import re
import typing as T
import threading

from terminedia.contexts import Context
from terminedia.utils import V2, Rect, get_current_tick

RETAIN_POS = object()


class StyledSequence:
    def __init__(
        self, text, mark_sequence, text_plane=None, context=None, starting_point=None
    ):
        """
        Args:
          text (Sequence): the stream of characters to be rendered  - it can be a string or a list of 1-grapheme strings.
          mark_sequence (Mapping): A mappign with Mark objects. The keys either represent index positions on the text
            where the mark will be processed, or they can be at the special index "config" denoting marks
            that are to have their indexes processed according to other enviroment circunstances
            (like the current "tick" - and possibly 'current position')
            The value at each item can contain a single Mark or a of Markers.
          text_plane (terminedia.text.planes.Text): area where the output is to be rendered
            on iterating. The Text object will be searched for aditional "Mark" objects that
            will compose the syle and position when encountered (they are less
            prioritary than the Marks passed in mark_sequence)
            If no Text object is given, the instance may still be iterated to retrieve
            a sequence of char, context and position - for example, when generating
            output directly to a tty.
          context (terminedia.Context): parent context. By default the context
          attached to the given text_plane is used
          starting_point: first position to be yielded when iteration starts (from which
            rules apply according to context.direction and others given by the matched
            "Mark" objects. Defaults to (0, 0)



        Helper class to render text that will both hold embedded style information,
        conveyed in "Mark" objects (with information like "at position 10, push foreground color 'red'"),
        and respect Mark objects embedded in the "text_plane" associanted rendering space.

        Style changes are all on top of a given "parent context"
        if any (otherwise, the text_plane context is used, or None)

        The rendering part include yielding the proper position of each
        rendering character,as contexts convey also
        text printing direction and marks can not only
        push a new printing direction, but also "teleport" the
        rendering point for the next character altogether.

        """
        self.text = text
        self.mark_sequence = mark_sequence
        self.parent_context = context
        self._last_index_processed = None
        self.context = Context()
        self.text_plane = text_plane
        self.starting_point = V2(starting_point) if starting_point else V2(0, 0)
        self.current_position = self.starting_point
        self._sanity_counter = 0
        self.locals = threading.local()

    def _process_to(self, index):

        if self._last_index_processed is None and index == 0:
            self.current_position = self.starting_point
        elif (
            self._last_index_processed is None
            or index != self._last_index_processed + 1
        ):
            return self._reprocess_from_start(index)

        for mark_here in self.marks.get_full(index, self.current_position):
            mark_here.context = self.context
            mark_here.pos = self.current_position
            if mark_here.attributes or mark_here.pop_attributes:
                self._context_push(mark_here.attributes, mark_here.pop_attributes)
            if mark_here.moveto:
                mtx = mark_here.moveto[0]
                mty = mark_here.moveto[1]
                mtx = mtx if mtx is not RETAIN_POS else self.current_position.x
                mty = mty if mty is not RETAIN_POS else self.current_position.y
                self.current_position = V2(mtx, mty)
            if mark_here.rmoveto:
                self.current_position += V2(mark_here.rmoveto)
        self._last_index_processed = index
        return self.context

    def _reprocess_from_start(self, index):
        self._sanity_counter += 1
        if self._sanity_counter > 1:
            raise RuntimeError(
                "Something resetting marked text internal state in infinite loop"
            )
        self._reset_context()
        self._last_index_processed = None
        for i in range(0, index + 1):
            self._process_to(i)

        self._sanity_counter -= 1
        return self.context


    def _enter_iteration(self):
        cm = self.locals.context_map = {}
        for key, value in self.context:
            cm[key] = [value]
        marks = self.text_plane.marks if self.text_plane else MarkMap()
        self.marks = marks.prepare(
            self.mark_sequence,
            self.text_plane.ticks if self.text_plane else get_current_tick(),
            self.text,
            self.context
        )


    def _context_push(self, attributes, pop_attributes):
        cm = self.locals.context_map
        changed = set()
        attributes = attributes or {}
        pop_attributes = pop_attributes or {}
        for key in pop_attributes:
            stack = cm.setdefault(key, [])
            if stack:
                changed.add(key)
                stack.pop()
        for key, value in attributes.items():
            stack = cm.setdefault(key, [])
            stack.append(value)
            changed.add(key)

        for attr in changed:
            if cm[attr]:
                setattr(self.context, attr, cm[attr][-1])
            else:
                pass

    def _get_position_at(self, char, index):
        if self._last_index_processed != index:
            self._process_to(index)
        position = self.current_position
        self.current_position += self.context.direction
        # TODO: handle double-width characters
        return position

    def __iter__(self):
        self._enter_iteration()
        with self.context():
            for index, char in enumerate(self.text):
                yield self.text[index], self._process_to(index), self._get_position_at(
                    char, index
                )
        if hasattr(self, "marks"):
            del self.marks
        # self._unwind()

    def _reset_context(self):
        for key, value in self._parent_context_data.items():
            if key in ("transformers", "pretransformers"):
                value = copy(value)
            setattr(self.context, key, value)

    def _prepare_context(self):
        self.context = Context()
        source = self.text_plane.owner.context
        self._parent_context_data = {key:value for key, value in source}
        self._reset_context()

    def render(self):
        if not self.text_plane:
            return
        # FIXME: if self.parent_context is not self.text_plane.owner.context, combine parent and current context
        # otherwise combination is already in place at the render_lock
        self._prepare_context()
        render_lock = self.text_plane._render_styled_lock(self.context)
        try:
            char_fn = next(render_lock)

            for char, context, position in self:
                char_fn(char, position)
        finally:
            next(render_lock, None)


class MarkMap(MutableMapping):
    """Mapping attached to each text plane -

    TL;DR: this is an internal mapping used to control
    rich text rendering and flow. An instance is attached
    to each text plane and can be reachd at shape.text[size].marks


    It contains Mark objects that
    are "virtually" hidden in the plane and can chang the attributes or
    position of any rich text that would be printed were they are located.

    The positional Marks can also be "virtual" in a sense one can set
    a rectangle of special marks in a single call: this is used
    to setup the "teleporter" marks at text-plane boundaries
    that enable text to continue on the next line, when printing
    left-to-right.

    A third Mark category can be added, consisting of Marks which index
    wll change overtime (a callable gets the "tick" number and that yields
    a 1D or 2D index for that Mark)

    The instances of MarkMap are consumed by StyledSequence objects when rendering,
    and those will set a 1D positional-mark mapping (this creates a shallow copy
    of a MarkMap instance). The StyledSequence then consumes marks when iterating
    itself for rendering, retrieving both marks in the text stream (1D positional
    marking), Marks fixed on the text plane, and special marks with time-variant
    position. When retrieving the Marks at a given position, the location on th
    2D plane, and tick number are available to be consumed by callables on
    special Mark objects


    """
    def __init__(self):
        self.data = {}
        self.tick = 0
        self.seq_data = {}
        self.special = set()
        self._concrete_special = {}

    def prepare(self, seq_data, tick=0, parsed_text="", context=None):
        instance = copy(self)
        instance.tick = tick
        instance.seq_data = seq_data
        instance.context = context
        instance.parsed_text = parsed_text
        instance.special = self.special.copy()
        if "special" in seq_data:
            instance.special.update(seq_data["special"])
        instance.concretize_special_marks()

        # self.data is the same object on purpose -
        return instance

    def concretize_special_marks(self):
        self._concrete_special = {}
        for mark in self.special:
            # TODO: inject parameters to compute index according to its signature
            # currently hardcoded to 2 parameters: tick and length of target text
            index = mark.index(self.tick, len(self.parsed_text))
            self._concrete_special.setdefault(index, []).append(mark)

    def get_full(self, seq_pos, pos):

        self.seq_pos = seq_pos
        self.pos = pos

        mark_seq = self._concrete_special.get(seq_pos, [])
        mark_seq += self._concrete_special.get(pos, [])
        mark_at_pos = self.seq_data.get(seq_pos, [])
        if not isinstance(mark_at_pos, Sequence):
            mark_at_pos = [mark_at_pos]
        mark_seq += mark_at_pos

        marks_plane = self.get(pos)
        if isinstance (marks_plane, Sequence):
            mark_seq = marks_plane + mark_seq
        elif isinstance(marks_plane, Mark):
            mark_seq.insert(0, marks_plane)


        return mark_seq

    def __setitem__(self, index, value):
        if isinstance(index, Rect):
            # TODO: enable lazy virtual Marks instead of these eager ones
            for pos in index.iter_cells():
                self[pos] = value
            return

        self.data[index] = value

    def __getitem__(self, index):
        # TODO retrieve MagicMarks and virtual marks
        return self.data[index]

    def __delitem__(self, index):
        del self.data[index]

    def __len__(self):
        return len(self.data)

    def __iter__(self):
        return iter(self.data)

    def __repr__(self):
        return "MarkMap < >"


class Mark:
    """Control object to be added to a text_plane or StyledStream

    The object indicate which context attributes or text position
    enter in effect at that point in the stream.

    Instances of this are to be automatically created on parsing markup strings or
    or other input - but can be hand-crafted for special effects.


    """

    # This is supposed to evolve to be programable
    # and depend on injected parameters like position, ticks -
    # like transformers.Transformer

    # For the time being, subclass and use 'property'.
    # 'context' and 'pos' attributes are set on the instance
    # prior to reading the other property values.

    __slots__ = "attributes pop_attributes moveto rmoveto context pos".split()
    attributes: T.Mapping
    pop_attributes: T.Mapping
    moveto: V2
    rmoveto: V2

    def __init__(self, attributes=None, pop_attributes=None, moveto=None, rmoveto=None):
        self.attributes = attributes
        self.pop_attributes = pop_attributes
        self.moveto = moveto
        self.rmoveto = rmoveto

    @classmethod
    def merge(cls, m1, m2):
        if not isinstance(m1, list):
            m1 = [m1]
        m1.append(m2)
        return m1

        # The following code is nice, and might still be used to
        # consolidate moveto + rmoveto -
        # However, it would not preserve the order of popping attibutes
        # so, we'd better allow Sequences with a single Key in the "mark_sequence" dictionary.
        #attributes = m1.attributes or {}
        #attributes.update(m2.attributes or {})
        #pop_attributes = m1.pop_attributes or {}
        #pop_attributes.update(m2.pop_attributes or {})
        #moveto = m2.moveto or m1.moveto
        #if m1.rmoveto and m2.rmoveto:
            #rmoveto = m1.rmoveto + m2.rmoveto
        #else:
            #rmoveto = m1.rmoveto or m2.rmoveto
        #return cls(
            #attributes=attributes,
            #pop_attributes=pop_attributes,
            #moveto=moveto,
            #rmoveto=rmoveto,
        #)

    def __repr__(self):
        return f"{self.__class__.__name__}({('attributes=%r, ' % self.attributes) if self.attributes else ''}{('pop_attributes=%r, ' % self.pop_attributes) if self.pop_attributes else ''}{('moveto={!r}, '.format(self.moveto)) if self.moveto else ''}{('rmoveto={!r}'.format(self.rmoveto)) if self.rmoveto else ''})"


EmptyMark = Mark()

class SpecialMark(Mark):
    __slots__=["index"]
    def __init__(self, index, *args, **kwargs):
        self.index = index
        super().__init__(*args, **kwargs)



class Tokenizer:
    pass


class MLTokenizer(Tokenizer):
    _parser = re.compile(r"(?<!\[)\[[^\[].*?\]")

    def __init__(self, initial=""):
        """Parses a string with special Markup and prepare for rendering

        After instantiating, keep calling '.update' to add more text,
        at any point call ".render()" to create a StyledSequence instance
        and render it to a text plane.
        """
        self.raw_text = ""
        self.update(initial)

    def update(self, text):
        # Imitates Python's hashlib interface
        self.raw_text += text

    def parse(self):
        """Parses the raw_text in  the instance, and sets
        setting a stripped "parsed_text" attribute along a ".mark_sequence" attribute
        containing the described marks embedded in the text as Mark instances.
        """
        raw_tokens = []
        offset = 0

        def annotate_and_strip_tokens(match):
            nonlocal offset
            token = match.group()
            raw_tokens.append((match.start() - offset, token.strip("[]")))
            offset += match.end() - match.start()
            return ""

        self.parsed_text = self._parser.sub(annotate_and_strip_tokens, self.raw_text)
        self._tokens_to_marks(raw_tokens)

    def _tokens_to_marks(self, raw_tokens):
        from terminedia.transformers import library as transformers_library
        from terminedia import Effects, Color, Directions, DEFAULT_BG, DEFAULT_FG, TRANSPARENT

        self.mark_sequence = {}
        for offset, token in raw_tokens:
            attributes = None
            pop_attributes = None
            rmoveto = None
            moveto = None

            token = token.lower()
            if ":" in token:
                action, value = [v.strip() for v in token.split(":")]
                if action == "effect":
                    action = "effects"
            else:
                action = token.strip()
                value = None
                if action in {"left", "right", "up", "down"}:
                    value = action
                    action = "direction"

            # Allow for special color values:
            if action in ("color", "foreground") and value == "default":
                value = DEFAULT_FG
            if action == "background" and value == "default":
                value = DEFAULT_BG
            if value == "transparent" and action in {"effects", "color", "foreground", "background"}:
                value = TRANSPARENT
            if value and value.startswith("(") and action in {"color", "foreground", "background"}:
                value = ast.literal_eval(value)

            attribute_names = {"effects", "color", "foreground", "background", "direction", "transformer", "char", "font", }
            if action in attribute_names:
                attributes = {
                    action: (
                        Color(value) if action in ("color", "foreground", "background") else
                        sum(Effects.__members__.get(v.strip(), 0) for v in value.split("|"))
                            if action == "effects" else
                        getattr(Directions, value.upper()) if action == "direction" else
                        getattr(transformers_library, value) if action == "transformer" else
                        value
                    )
                }
            if action[0] == "/" and action[1:] in attribute_names:
                pop_attributes = {action.lstrip("/"): None}

            if "," in action and attributes is None and pop_attributes is None:
                nx, ny = [v.strip() for v in action.split(",")]
                nnx, nny = int(nx), int(ny)
                if nx[0] in ("+", "-") and ny[0] in ("+", "-"):
                    rmoveto = nnx, nny
                elif nx[0] in ("+", "-") and ny[0] not in ("+", "-"):
                    moveto = RETAIN_POS, nny
                    rmoveto = nnx, 0
                elif nx[0] not in ("+", "-") and ny[0] in ("+", "-"):
                    moveto = nnx, RETAIN_POS
                    rmoveto = 0, nny
                else:
                    moveto = nnx, nny
            # Unknown token action - simply drop for now"
            mark = Mark(attributes, pop_attributes, moveto, rmoveto)
            if offset in self.mark_sequence:
                mark = Mark.merge(self.mark_sequence[offset], mark)
            self.mark_sequence[offset] = mark

    def __call__(self, text_plane=None, context=None, starting_point=(0, 0)):
        self.parse()
        self.styled_sequence = StyledSequence(
            self.parsed_text,
            self.mark_sequence,
            text_plane=text_plane,
            context=context,
            starting_point=starting_point,
        )
        return self.styled_sequence


class ANSITokenizer(Tokenizer):
    pass
