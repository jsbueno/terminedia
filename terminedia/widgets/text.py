from collections import namedtuple
from copy import deepcopy
import itertools
from math import ceil
from threading import RLock
from warnings import warn

import terminedia

from terminedia import Mark, Transformer

from terminedia import V2, Rect, Directions

from terminedia.events import EventSuppressFurtherProcessing
from terminedia.input import KeyCodes
from terminedia.utils import ClassCache
from terminedia.utils.gradient import RangeMap
from terminedia.text import escape

from .core import  Widget, OVERFILL, UNREACHABLE, _ensure_extend



_NOT_FOUND = object()
_EMPTY_MARK = Mark()
_UNUSED = "*"
_USED = " "
_ENTER = "#"

MarkCell = namedtuple("MarkCell", "from_pos to_pos flow_changed is_used direction normalized_pos")
BackTrack = namedtuple("BackTrack", "position direction distance_to_closest_mark mark_count")


class CursorTransformer(terminedia.Transformer):
    blink_cycle = 8

    def __init__(self, parent, insert_effect="reverse", overwrite_effect="underline"):
        self.parent = parent
        self.effect_table = {
            False: terminedia.Effects(overwrite_effect),
            True: terminedia.Effects(insert_effect)
        }

        super().__init__()

    # FIXME: cursor effects are leaking for the sprite -
    # possible problem in handling the context in text.plane
    def effects(self, value, pos, tick):
        effect = self.effect_table[self.parent.insertion]
        if effect != terminedia.Effects.blink and (not self.parent.parent.focus or not tick % self.blink_cycle):
            return value
        size = self.parent.text.char_size
        pos -= (self.parent.text.pad_left, self.parent.text.pad_top)
        if size == (1,1):
            if pos != self.parent.pos:
                return value
        else:
            rect = Rect(self.parent.pos * size, width_height=size)
            if pos not in rect:
                return value

            if effect == terminedia.Effects.underline and int(pos.y) != ceil(rect.bottom - 1):
                return value
        return (value if isinstance(value, terminedia.Effects) else 0) | effect


    #def background(self, value, pos, tick):
        #if not self.parent.focus or pos != self.parent.pos or not tick % 7:
            #return value
        #return (127, 127, 0)
        #return (value if isinstance(value, terminedia.Effects) else 0)| self.effect

def _ensure_sequence(mark):
    return [mark,] if isinstance(mark, Mark) else mark

def _count_empty_at_end(seq):
    return sum(1 for _ in itertools.takewhile(lambda x: not x, reversed(seq)))


class LinesList(list):
    # class to contain prefix and postfix text content of a larger than displayed
    # text widget

    def __init__(self, *args):
        self.prefix_newline = False
        self.postfix_newline = False
        super().__init__(*args)

    @property
    def value(self):
        return "\n" * self.prefix_newline * bool(self) + "\n".join(self) + "\n" * self.postfix_newline * bool(self)

    def clear(self):
        self.prefix_newline = self.postfix_newline = False
        self[:] = []

    def load(self, value: str):
        self.clear()
        if not value:
            return
        if value[0] == "\n":
            self.prefix_newline = True
            value = value[1:]
            if not value:
                return
        if value[-1] == "\n":
            self.postfix_newline = True
            value = value[:-1]
        self[:] = value.split("\n")

    def transfer(self, index, size, dest):
        newline = True
        if len(self[index]) > size:
            value = self[index][:size]
            self[index] = self[index][size:]
            newline = False
        else:
            value = self.pop(index)
            # do not add an empty line do an empty buffer: keep it empty
            if value == '' and not dest:
                return False
        if index == 0:
            if self.prefix_newline or dest.postfix_newline or not dest:
                dest.append(value)
            else:
                dest[-1] += value
            dest.postfix_newline = newline
            #self.prefix_newline = newline
        elif index == -1:
            if self.postfix_newline or dest.prefix_newline or not dest:
                dest.insert(0, value)
            else:
                dest[0] = value + dest[0]
            dest.prefix_newline = newline
            #self.postfix_newline = newline
        return newline

    @property
    def length(self):
        return len(self.value)

###############
#
# Text Editing Guts
#
##############

def map_text(text, pos, direction):
    """Used internally by "Editable". Given a text plane, maps out the way that each reachable cell can be acessed

    The map re-interprets the Marks that affect text flow found on the text plane -
    but Marks with "special_index" and other kinds of dynamic marks will likely
    be missed by this mapping.


    With the map, afterwards, given
    a cell position, one can backtrack to know the distance of the last typed character,
    and on which softline it is
    """
    # FIXME: currently the implementation of Styled text rendering
    # does not behave properly if a Mark moves the flow
    # to a cell containing another teleporting mark:
    # the target mark is ignored.
    # The algorithm bellow do the right thing -  it has to be implemented
    # in rendering as well
    pos = V2(pos)
    direction = V2(direction)
    last_cell = MarkCell(None, pos, False, True, direction, V2(0,0))
    from_map = {pos: [last_cell] }
    to_map = {None: [last_cell] }
    rect = terminedia.Rect((0, 0), text.size)
    counter = 0
    marks = _ensure_sequence(text.marks.abs_get(pos, _EMPTY_MARK,))
    normalized_lines_map = {V2(0,0): last_cell}
    normalized_x = 1
    normalized_y = 0
    while True:
        prev_pos = pos

        pos, direction, flow_changed, position_is_used = text.marks.move_along_marks(prev_pos, direction)

        if flow_changed:
            normalized_x = 0
            normalized_y += 1
        npos = V2(normalized_x, normalized_y)

        cell = MarkCell(prev_pos, pos, flow_changed, position_is_used, direction, npos)
        from_map.setdefault(pos, []).append(cell)
        to_map.setdefault(prev_pos, []).append(cell)
        normalized_lines_map[npos] = cell

        counter += 1
        marks = _ensure_sequence(text.marks.abs_get(pos, _EMPTY_MARK,))
        if marks[0] is _EMPTY_MARK and pos not in rect or counter > 3 * rect.area:
            # we can have a text flow that goes through each position more than once,
            # but we have to halt it at some point - hence the "3 *" above.
            break
        normalized_x += 1

    return to_map, from_map, normalized_lines_map


class TextDoesNotFit(IndexError): #sentinel
     pass

class JoinLines(BaseException):
    def __init__(self, line):
        self.line = line

lcache = ClassCache()

class Lines:
    # helper class closely tied to Editable
    def __init__(self, value, parent):
        self.parent= parent
        self.soft_lines = LinesList()
        self.reload(value)
        self._last_event = (None, None, None, None, None)

    @lcache.invalidate
    def _hard_load_from_soft_lines(self):
        # set text in text_plane from parent from text in value,
        # filling in spaces for unused values.
        new_hard_lines = []
        for i, line in enumerate(self.soft_lines):
            hard_len = self._hard_line_capacity_for_given_soft_line(i)
            new_hard_lines.append(line + " " * (hard_len - len(line)))

        raw_value = "".join(new_hard_lines)
        if len(raw_value) > self.parent.text_space:
            raise TextDoesNotFit()
        self.parent.raw_value = raw_value

    def reload(self, value=None):
        if value is None:
            value = self.soft_lines[:]
        if isinstance(value, str):
            value = value.split("\n")
        if len(value) < self.len_hard_lines:
            value.extend([""] * (self.len_hard_lines - len(value) - 1))
        self.soft_lines[:] = value
        self._hard_load_from_soft_lines()
        self.is_there_display_space = False

    def _count_empty_hardlines(self, lines):
        soft_index = 0
        soft_line = lines[soft_index]
        count = 0
        for hard_line in self.hard_lines:
            soft_line = soft_line[len(hard_line):]
            if not soft_line:
                soft_index += 1
                if soft_index < len(lines):
                    soft_line = lines[soft_index]
                else:
                    soft_line = ""
                    count += 1
        if count > 0:
            count -= 1
        return count

    @lcache.cached
    def _soft_lines_spams(self):
        hard_lines = self.hard_lines
        spams = []
        hard_line_index = -1
        acc = -1
        hard_line_map = {}
        soft_line_map = {}
        hard_line_indexes = [0,]
        for i, line in enumerate(self.soft_lines):
            this_line_spam = 0
            offset = 0
            soft_line_map[i] = hard_line_index + 1
            while len(line) > acc:
                hard_line_index += 1
                if hard_line_index >= len(hard_lines):
                    if not line and i == len(self.soft_lines) - 1:
                        self.soft_lines.pop()
                    break
                hard_line_map[hard_line_index] = (i, offset)
                len_hard_line = len(hard_lines[hard_line_index])
                acc += len_hard_line + (1 if acc == -1 else 0)
                hard_line_indexes.append(len_hard_line + hard_line_indexes[-1])
                this_line_spam += 1
                offset += 1
            if len(line) == acc and i == len(self.soft_lines) - 1:
                this_line_spam += 1
                hard_line_index += 1
                if hard_line_index < len(hard_lines):
                    hard_line_map[hard_line_index] = (i, offset + 1)
                    len_hard_line = len(hard_lines[hard_line_index])
                    hard_line_indexes.append(len_hard_line + hard_line_indexes[-1])

            spams.append(this_line_spam)
            acc = -1
        return spams, hard_line_map, soft_line_map, hard_line_indexes

    @lcache.cached_prop
    def soft_lines_spams(self):
        return self._soft_lines_spams()[0]

    @lcache.cached_prop
    def hard_line_map(self):
        return self._soft_lines_spams()[1]

    @lcache.cached_prop
    def soft_line_map(self):
        return self._soft_lines_spams()[2]

    @lcache.cached_prop
    def hard_line_indexes(self):
        return self._soft_lines_spams()[3]

    @lcache.cached_prop
    def len_hard_lines(self):
        return len(self.parent.line_indexes.stops)

    @lcache.cached_prop
    def hard_lines(self):
        start = 0
        lines = []
        for end in self.parent.line_indexes.stops[1:]:
            line = "".join(cell for cell in self.parent.raw_value[start:end])
            if len(line) < end - start:
                line += " " * ((end - start) - len(line))
            lines.append(line)
            start = end
        return lines

    def hard_line_number(self, index):
        acc = 0
        for i, line in enumerate(self.hard_lines):
            acc += len(line)
            if index < acc:
                return i
        raise TextDoesNotFit()

    def get_index_in_soft_line(self, hard_index):
        acc = 0
        for i, line in enumerate(self.hard_lines):
            new_acc = acc + len(line)
            if new_acc > hard_index:
                hard_line_number = i # byproduct. consolidate later.
                index_in_current_hard_line = hard_index - acc
                break
            acc = new_acc
        else:
            raise TextDoesNotFit()
        offset = self.hard_line_map[hard_line_number][1]
        previous_hard_line = hard_line_number
        index_in_soft_line = index_in_current_hard_line
        while offset and previous_hard_line:
            previous_hard_line -= 1
            offset -= 1
            index_in_soft_line += len(self.hard_lines[previous_hard_line])
        soft_line = self.hard_line_map[hard_line_number][0]
        return soft_line, index_in_soft_line

    def set(self, pos, value):
        return self._set(pos, value, insert=False)

    def insert(self, pos, value):
        return self._set(pos, value, insert=True)

    def _hard_line_capacity_for_given_soft_line(self, line):
        try:
            hard_line_index = self.soft_line_map[line]
        except KeyError:
            return 0
        disconsider_last_soft_lines = 0
        done = False
        while not done:
            try:
                result = sum(len(self.hard_lines[j]) for j in range(hard_line_index, hard_line_index + self.soft_lines_spams[line] - disconsider_last_soft_lines))
            except IndexError:
                if not disconsider_last_soft_lines:
                    disconsider_last_soft_lines = 1
                else:
                    raise TextDoesNotFit()
            else:
                done = True
        return result

    def _soft_line_exceeded_space(self, line):
        length = self._hard_line_capacity_for_given_soft_line(line)
        return len(self.soft_lines[line]) > length

    def at_last_line(self, pos):
        index = self.parent.indexes_to[pos]
        line, index = self.get_index_in_soft_line(index)
        return line == len(self.soft_lines) - 1

    @property
    def is_there_display_space(self):
        # this avoids an infinite loop of "enter" insertion -
        # it is set in Editable just once, before repeating
        # an "Enter" key after scrolling the last visible line to text_postfix
        return self._is_there_display_space and self._is_there_display_space_tick + 1 <= self.parent.tick

    @is_there_display_space.setter
    def is_there_display_space(self, value):
        self._is_there_display_space = value
        self._is_there_display_space_tick = self.parent.tick

    @lcache.invalidate
    def _set(self, hard_index, value, insert):
        prev = deepcopy(self.soft_lines)

        line, index =(self.get_index_in_soft_line(hard_index))
        dist_from_eol = index - len(self.soft_lines[line])
        if value == KeyCodes.ENTER:
            if insert:
                if not self.soft_lines[-1] and line < len(self.soft_lines) - 1 and not self.parent.text_postfix or self.is_there_display_space:
                    self.soft_lines.insert(line + 1, self.soft_lines[line][index:])
                    self.soft_lines[line] = self.soft_lines[line][:index]
                    self.soft_lines.pop()
                else:
                    raise TextDoesNotFit()
            hard_index = self.hard_line_indexes[self.soft_line_map[line] + self.soft_lines_spams[line]]
        elif dist_from_eol == 0:
            if index == 0 and line > 0:
                # First element in a line, we might be typing from a previous line and have
                # to merge the current line into the previous soft_line
                if (
                    # self._last_event[1] == line - 1 and
                    # self._last_event[2] >= len(self.soft_lines[line - 1]) - 1 and
                    self._last_event[3] == self.parent.tick - 1 and
                    self._last_event[4] != KeyCodes.ENTER
                ):
                    line -= 1
                    index = len(self.soft_lines[line])

            # this is the same in insertion mode and setting mode
            # but when we hit a hard-line boundary there is more stuff to be done
            self.soft_lines[line] += value
            if self._soft_line_exceeded_space(line):
                if insert:
                    if not self.soft_lines[-1] and not self.parent.text_postfix or self.is_there_display_space:
                    #if not self.soft_lines[-1]:
                        self.soft_lines.pop()
                    else:
                        raise TextDoesNotFit()
                else: # detect hard-line break instead of "False":
                    # merge the two softlines, eat, first char in the next one
                    old_content = self.soft_lines[line + 1]
                    del self.soft_lines[line + 1]
                    if old_content:
                        self.soft_lines[line] += old_content[1:]
        elif dist_from_eol < 0:
            line_text = self.soft_lines[line]
            self.soft_lines[line] = line_text[:index] + value + line_text[index + int(not insert):]
        else:
            self.soft_lines[line] += (" " * dist_from_eol if not insert else "") +  value
            if insert:
                hard_index -= dist_from_eol

        if len(self.soft_lines[line]) > self._hard_line_capacity_for_given_soft_line(line):
            if not self.soft_lines[-1] and not self.parent.text_postfix or self.is_there_display_space:
            # if not self.soft_lines[-1]: # and not self.editable.text_postfix or self.is_there_display_space:
                self.soft_lines.pop()
                self.soft_lines_spams.pop()
            self.soft_lines_spams[line] += 1

        try:
            self._hard_load_from_soft_lines()
        except TextDoesNotFit:
            self.soft_lines[:] = prev
            self._hard_load_from_soft_lines()
            raise
        self._last_event = (hard_index, line, index, self.parent.tick, value)
        return hard_index

    @lcache.invalidate
    def del_(self, hard_index, backspace, insert=True):

        # prev = deepcopy(self.soft_lines)

        line, index =(self.get_index_in_soft_line(hard_index))
        dist_from_eol = index - len(self.soft_lines[line])
        if dist_from_eol == 0 and backspace:
            self.soft_lines[line] = self.soft_lines[line][:-1]
        elif dist_from_eol == 0 and not backspace:
            # merge next softline
            if line < len(self.soft_lines) - 2:
                self.soft_lines[line] += self.soft_lines[line + 1]
                del self.soft_lines[line + 1]
                self.soft_lines.extend([""] * self._count_empty_hardlines(self.soft_lines))

        elif dist_from_eol < 0:
            line_text = self.soft_lines[line]
            self.soft_lines[line] = line_text[:index] + line_text[index + 1:]
        elif dist_from_eol > 0 and not backspace:
            # join two lines - have to be done at editable level due to suffix text.
            raise JoinLines(line)
        elif backspace and insert:
            self.soft_lines[line] = self.soft_lines[line][:-1]
            hard_index -= dist_from_eol

        if backspace:
            hard_index -= 1
        try:
            self._hard_load_from_soft_lines()
        except TextDoesNotFit:
            pass
        self._last_event = (None, None, None, None, None)

        return hard_index

    @property
    def displayed_value(self):
        result = ""
        empty_counter = 0
        for i, line in enumerate(self.soft_lines):
            if not line:
                empty_counter += 1
                continue
            result += "\n" * empty_counter + line
            empty_counter = 1
        return result

####
# super refactor

class InnerSeqLine:
    def __init__(self, grandparent, index):
        self.grandparent = grandparent
        self.index = index

    @property
    def value(self):
        y = self.index
        i = 0
        val = ""
        while True:
            try:
                val += self.grandparent[i, y]
            except (KeyError, IndexError):
                break
            i += 1
        return val

    @value.setter
    def value(self, text):
        y = self.index
        x = 0

        for x, char in enumerate(text):
            try:
                self.grandparent[x, y] = char
            except (IndexError, KeyError):
                raise TextDoesNotFit("Text won't fit in mapped line. Error at index:", x)

    # TBD: cache this
    @property
    def size(self):
        y = self.index
        x = 0
        while True:
            try:
                self.grandparent[x, y]
            except (IndexError, KeyError):
                break
            x += 1
        return x

    def __getitem__(self, index):
        return self.value[index]

    def __setitem__(self, index, value):
        val = list(self.value)
        val[index] = value
        self.value = val

    def clear(self):
        y = self.index
        for x in range(self.size):
            self.grandparent[x, y] = " "

    def __len__(self):
        return self.size

    def __str__(self):
        return self.value


class InnerSeqLinesContainer:
    def __init__(self, parent):
        self.parent = parent

        self.data = []
        y = 0

        while True:
            try:
                self.parent[0, y]
            except (KeyError, IndexError):
                break
            self.data.append(InnerSeqLine(self.parent, y))
            y += 1
        self.length = y

    def __len__(self):
        return self.length

    def __getitem__(self, index):
        return self.data[index]


class InnerSeq:
    def __init__(self, source, map):
        self.source = source
        self.map = map
        self.rev_map = {v: k for k, v in map.items()}
        self.lines = InnerSeqLinesContainer(self)

    def __getitem__(self, index):
        return self.source[self.map[index]]

    def __setitem__(self, index, value):
        self.source[self.map[index]] = value

    def __len__(self):
        return len(self.map)

from collections import UserList
from collections.abc import MutableSequence

class EditableLinesChars(MutableSequence):
    def __init__(self, parent):
        self.parent = parent
        self.grandparent = parent.parent

    def __getitem__(self, pos):
        return self.parent[pos[1]][pos[0]]

    def __setitem__(self, pos, value):
        x = pos[0]
        line = self.parent[pos[1]]
        self.parent[pos[1]] = line[:x] + value + line[x + len(value):]

    def __delitem__(self, pos):
        line = list(self.parent[pos[1]])
        del line[pos[0]]
        self.parent[pos[1]] = "".join(line)

    def insert(self, pos, value):
        x = pos[0]
        line = self.parent[pos[1]]
        self.parent[pos[1]] = line[:x] + value + line[x + len(value):]

    def __len__(self):
        return sum(len(line) for line in self.parent)

class EditableLines(UserList):
    def __init__(self, *args, parent, **kw):
        self.parent = parent
        self.chars = EditableLinesChars(self)
        super().__init__(*args, **kw)


class SoftLines:
    def __init__(self, text_plane, value="", initial_position=V2(0, 0), direction=Directions.RIGHT, offset=0, max_lines=None, max_text_size=None):
        """[WIP] Inner class bridging larger than display text content to physical
        displayed text in a TextPlane with arbitrary display layout.

        XXX: move to terminedia.text.plane ??
        """

        self.lock = RLock()
        self.text_plane = text_plane
        self.cursor = self.initial_position = initial_position
        self.direction = self.initial_direction = direction

        self.offset = offset
        self.pre = []
        if isinstance(value, str):
            value = value.split("\n")

        _empty_lines = _count_empty_at_end(value)
        if _empty_lines:
            value = value[:-_empty_lines]
            value_ends_on_newline = True
        else:
            value_ends_on_newline = False

        self.editable = EditableLines(value if isinstance(value, list) else value.split("\n"), parent=self)
        self.post = []
        self.first_line_offset = 0
        self.last_line_length = 0

        self.editable_line_lengths = []

        self.max_lines = max_lines
        self.max_text_size = max_text_size

        self.text_pathto_map, self.text_path_map, self.normalized_lines = map_text(text_plane, self.initial_position, direction)

        self.physical_cells = text_plane
        self.hard_cells = InnerSeq(self.physical_cells, {k: v.to_pos for k, v in self.normalized_lines.items()})
        self.hard_lines = self.hard_cells.lines

        self.last_line_explicit_lf = (
            self.editable and
            self.can_end_in_lf and
            value_ends_on_newline
        )
        self.reflow()

    @property
    def can_end_in_lf(self):
        return len(self.hard_lines) > 1 or isinstance(self.max_lines, int) and self.max_lines > 1

    def _reflow_pre(self):
        text = [*self.pre, *self.editable, *self.post]
        new_pre = []
        first_line_offset = 0
        remaining_offset = self.offset
        while remaining_offset:
            if not text:
                break
            if len(text[0]) <= remaining_offset:
                new_pre.append(text.pop(0))
                remaining_offset -= len(new_pre[-1])
                continue
            first_line_offset = remaining_offset
            remaining_offset = 0
        self.first_line_offset = first_line_offset
        self.pre = new_pre
        self.editable[:] = text

    def _reflow_main_inner(self, line, hard_line):
        initial_line = line
        cumulative_transcribe = 0
        while line:
            len_hard_line = len(hard_line)
            transcribe = min(len_hard_line, len(line))
            hard_line[0:transcribe] = line[0:transcribe]
            if len_hard_line < len(line):
                line = line[transcribe:]
                cumulative_transcribe += transcribe
                self._transient_last_line_length = cumulative_transcribe
                hard_line = next(self._transient_lines_iter)
            else:
                hard_line[transcribe: len_hard_line] = " " * (len_hard_line - transcribe)
                line = ""
        self._transient_last_line_length = len(initial_line)
        hard_line = next(self._transient_lines_iter)
        hard_line.clear()
        return hard_line

    def _reflow_main(self):
        self._transient_lines_iter = iter(self.hard_lines)
        hard_line = next(self._transient_lines_iter)
        if not self.editable:
            self.last_line_length = 0
            return 0, False
        for i, line in enumerate(self.editable):
            if i == 0:
                line = line[self.first_line_offset:]
            try:
                hard_line = self._reflow_main_inner(line, hard_line)
            except StopIteration:
                self.last_line_length = self._transient_last_line_length + (self.first_line_offset if i == 0 else 0)
                return i, True
        for hard_line in self._transient_lines_iter:
            hard_line.clear()
            # just clear if there is at least one line slacking
        self.last_line_length = (len(self.editable[-1])) if self.editable else 0
        return i, False

    def _reflow_post(self, last_line, hard_lines_exhausted):
        self.post[:] = []
        if (
            not self.editable or
            len(self.editable) <= len(self.hard_lines) and
            not hard_lines_exhausted and
            last_line <= len(self.editable) - 1
        ):
            return
        if self.max_text_size is None and self.max_lines is None:
            raise TextDoesNotFit("Chars are restricted to text_plane cells. Use a custom max_text_size or max_lines to allow larger text content.")
        if self.editable[last_line + 1:]:
            self.post[:] = self.editable[last_line + 1:]
            self.editable[last_line + 1:] = []
            #self.last_line_explicit_lf = True
        else:
            self.last_line_explicit_lf = False
        if self.max_lines is not None and len(self.post) + len(self.pre) + len(self.editable) > self.max_lines:
            raise TextDoesNotFit("Text takes more lines than available.Increase 'max_lines'")
        if self.max_text_size is not None and len(self.value) > self.max_text_size:
            raise TextDoesNotFit("Too many characters")

    def reflow(self):
        with self.lock:
            self._reflow_pre()
            last_line_displayed, exhausted = self._reflow_main()
            self._reflow_post(last_line_displayed, exhausted)

    @property
    def value(self):
        text = "\n".join(self.pre)
        if text:
            text += "\n"
        text += "\n".join(self.editable)
        if self.post:
            text += "\n" + "\n".join(self.post)
        if self.last_line_explicit_lf and self.can_end_in_lf:
            text += "\n"
        elif text and text[-1] == "\n":
            text = text[:-1]
        return text

    @property
    def displayed_value(self):
        if len(self.editable) > 1:
            text = "\n".join([self.editable[0][self.first_line_offset:], *self.editable[1:-1], self.editable[-1][:self.last_line_length]])
        else:
            text = self.editable[0][self.first_line_offset:self.last_line_length] if self.editable else ""
        if (
            not self.post and self.last_line_explicit_lf or
            self.post and len(self.editable[-1]) == self.last_line_length
        ):
            text += "\n"
        return text

    def scroll_char_left(self, n=1):
        self.offset += n
        self.reflow()

    def scroll_char_right(self, n=1):
        self.offset = max(self.offset - n, 0)
        self.reflow()

    def scroll_line_up(self, n=1):
        offset = self.offset
        if not self.editable:
            return
        delta = min(len(self.editable[0]) - self.first_line_offset, len(self.hard_lines[0]))
        self.offset += delta

        self.reflow()
        if n > 0 and n > 1:
            return self.scroll_line_down(n - 1)


    def scroll_line_down(self, n=1):
        if not self.pre and self.first_line_offset == 0:
            return
        offset = self.offset
        line_len = len(self.hard_lines[0])
        if self.first_line_offset >= line_len:
            offset -= line_len
        elif self.first_line_offset:
            offset -= self.first_line_offset
        elif self.pre:
            offset -= min(line_len, len(self.pre[-1]))
        self.offset = offset
        self.reflow()
        if n > 0 and n > 1:
            return self.scroll_line_down(n - 1)

    def __len__(self):
        return len(self.value)

# end superrefactor
#######

class Editable:
    """Internal class to text widgets -
    responsible for managing a keyboard-event-echo-in-text-plane
    pattern. Use text-editing subclasses of Widget instead of this.

    You may re-initialize the widget.editable instance if you make layout changes
    to the underlying shape (text-flow Marks) after the widget is instantiated.
    """
    def __init__(self, text_plane, parent=None, value="", pos=None, line_sep="\n", text_size=None, offset=0):
        self.focus = True
        self.initial_pos = self.pos = pos or V2(0, 0)
        self.text = text_plane
        self.parent = parent
        self.line_sep = line_sep
        self.insertion = True
        self.context = self.text.owner.context
        self.initial_direction = self.context.direction
        self.tick = 0

        if parent:
            self.parent.sprite.transformers.append(CursorTransformer(self))
        self.last_rendered_cursor = None
        self.last_text_data = []
        self.text_pathto_map, self.text_path_map, self.normalized_lines = map_text(self.text, self.initial_pos, self.context.direction)

        self.impossible_pos = False


        # properties used to edit text larger than the display-size:
        self.display_size = len(self.text_path_map) - 1
        if text_size is None or text_size < self.display_size - 1:
            if text_size and text_size < self.display_size - 1:
                warn("Smaller than display widget text size not implemented.")
            text_size = self.display_size - 1
            self.larger_than_displayed = False
        else:
            self.larger_than_displayed = True
        self.text_size = text_size
        self.text_prefix = LinesList()
        self.text_postfix = LinesList()


        # resume building initial internal-state
        self._build_shape_indexes()
        self.lines = Lines(value, self)
        self.text_size = text_size
        # state to indicate if insertion point at last cell
        # should be _after_ or _before_ last character
        self.text_past_end = False

        self.value = value
        self.text_offset = offset

    def _build_shape_indexes(self):
        pos = self.initial_pos
        indexes_to = {}
        indexes_from = {}
        new_line_indexes = [0]
        pos_at_new_lines = [pos]
        cells_at_lines = [[]]
        count = 0
        index_counted = False
        while True:
            indexes_from[count] = pos
            indexes_to[pos] = count
            cells_at_lines[-1].append(pos)
            count += 1
            try:
                cell = self.text_pathto_map[pos][0]
            except KeyError:
                break
            if cell.flow_changed: #not cell.is_used:
                new_line_indexes.append(count)
                pos_at_new_lines.append(pos)
                index_counted = True
                cells_at_lines.append([])
            else:
                index_counted = False
            pos = cell.to_pos
        if not index_counted:
            new_line_indexes.append(count - 1)
            # pos_at_new_lines.append(pos)
        self.raw_value = " " * len(indexes_from)
        self.line_indexes = RangeMap(new_line_indexes)
        self.indexes_from = indexes_from
        self.indexes_to = indexes_to
        self.pos_at_new_lines = pos_at_new_lines
        self.cells_at_lines = cells_at_lines

    def cursor_to_previous_shape_line(self):
        norm_cell = self.text_path_map[self.pos][0].normalized_pos
        if norm_cell.y == 0:
            return
        norm_cell -= (0,1)
        self.pos = self.normalized_lines[norm_cell].to_pos

    def cursor_to_next_shape_line(self):
        ...

    @property
    def text_space(self):
        return len(self.indexes_from) - 1

    def get_next_pos_from(self, pos, direction="forward"):
        if direction == "forward":
            return self.text_pathto_map[pos][0].to_pos
        return self.text_path_map[pos][0].to_pos

    @property
    def displayed_value(self):
        return self.lines.displayed_value

    @property
    def value(self):
        if self.text_size > self.display_size:
            if self.text_postfix:
                empty_lines = "\n" * _count_empty_at_end(self.lines.soft_lines)
            else:
                empty_lines = ""
            return self.text_prefix.value + self.displayed_value + empty_lines + self.text_postfix.value
        else:
            return self.displayed_value

    @value.setter
    def value(self, text):
        self.set_value_with_offset(text, self.text_offset)

    def set_value_with_offset(self, text, text_offset):
        if text_offset and not self.larger_than_displayed:
            raise valueError("Can't set a text offset for widgets that should display all its contents")
        off = text_offset
        if len(text) > self.text_size:
            raise TextDoesNotFit
        prev_value = self.value
        ds = self.display_size
        pre, editable, post = text[:off], text[off:off + ds], text[off + ds:]
        if editable.count("\n") >= len(self.lines.hard_lines):
            max_lines = len(self.lines.hard_lines)
            editable_lines = editable.split("\n")
            editable = "\n".join(editable_lines[:max_lines])
            post = "\n" + "\n".join(editable_lines[max_lines:]) + post
        self.text_prefix.load(pre)
        self.text_postfix.load(post)
        self.lines.reload(editable)
        self.regen_text()

    @property
    def shaped_value(self):
        return self.text.shaped_str

    def keypress(self, event):
        try:
            self.change(event)
        finally:
            # do not allow keypress to be processed further
            raise EventSuppressFurtherProcessing()

    def scroll_char_right(self):
        if not self.larger_than_displayed:
            return
        self.text_offset -= 1

    def scroll_char_left(self):
        if not self.larger_than_displayed:
            return
        self.text_offset += 1

    def scroll_line_up(self):
        self._scroll_line(direction="up")

    def scroll_line_down(self):
        self._scroll_line(direction="down")

    def _scroll_line(self, direction):
        if direction == "up":
            target = self.text_prefix
            source = self.text_postfix
            outgoing_edge = 0
            incoming_edge = -1
        else:
            target = self.text_postfix
            source = self.text_prefix
            outgoing_edge = -1
            incoming_edge = 0

        if not self.lines.soft_lines:
            return
        # put first hard or soft line from display into prefix
        size = len(self.lines.hard_lines[outgoing_edge])
        self.lines.soft_lines.transfer(outgoing_edge, size, target)
        # move first soft or hardline from postfix into display
        prefix_size = size
        if source:
            size = len(self.lines.hard_lines[incoming_edge])
            if prefix_size != size:
                warn("Attempting to scroll up text on a non rectangular text shape. This is not an implemented edge case - mayhem may ensue!")
            source.transfer(outgoing_edge, size, self.lines.soft_lines)
        else:
            if direction == "up":
                # self.lines.soft_lines.append('')
                pass
            else:
                # TBD: might break with softlines > hard_lines
                self.lines.soft_lines.insert(0, '')
        self.lines.reload()
        self.regen_text()

    @property
    def text_offset(self):
        return self.text_prefix.length

    @text_offset.setter
    def text_offset(self, new_offset):
        self.set_value_with_offset(self.value, new_offset)

    def scroll_last_line_down(self):
        last_line = self.lines.soft_lines.pop()
        self.text_postfix.insert(0, last_line)
        self.text_postfix.prefix_newline = True
        self.lines.soft_lines.append('')
        self.lines.reload()
        self.regen_text()
        self.lines.is_there_display_space = True

    def join_lines(self, displayed_line):
        lines = self.displayed_value.split("\n")
        lines[displayed_line] += (lines.pop(displayed_line + 1) if len(lines) > displayed_line else '')
        self.lines.reload(lines)

    def change(self, event=None, key=None):
        """Called on each keypress when the widget is active. Take 2"""

        self.tick += 1

        key = event.key if event else key
        valid_symbol = True

        if key in (KeyCodes.UP, KeyCodes.DOWN, KeyCodes.LEFT, KeyCodes.RIGHT):
            index = self.indexes_to[self.pos]
            if key == KeyCodes.RIGHT:
                self.text_past_end = False
                if self.pos.x < self.text.size.x - 1:
                    self.pos = self.text.extents(self.pos, " ", direction="right")
                else:
                    if len(self.lines.hard_lines) == 1:
                        try:
                            self.scroll_char_left()
                        except TextDoesNotFit:
                            return
                    else:
                        if index < len(self.indexes_from) - 2:
                            new_pos = self.indexes_from[index + 1]
                            if new_pos in self.text.rect:
                                self.pos = new_pos
                        elif len(self.value) > self.text_offset + len(self.displayed_value):
                            self.scroll_char_left()
                            self.text_past_end = True
                        else:
                            self.text_past_end = True
            if key == KeyCodes.LEFT:
                self.text_past_end = False
                if self.pos.x > 0:
                    self.pos = self.text.extents(self.pos, " ", direction="left")
                elif index > 0:
                    self.pos = self.indexes_from[index -1]
                elif self.text_offset > 0:
                    self.scroll_char_right()

            if key == KeyCodes.UP:
                if self.pos.y > 0:
                    self.pos = self.text.extents(self.pos, " ", direction="up")
                elif self.text_prefix:
                    self.scroll_line_down()
            elif key == KeyCodes.DOWN:
                if self.pos.y < self.text.size.y - 1:
                    self.pos = self.text.extents(self.pos, " ", direction="down")
                elif self.text_postfix:
                    self.scroll_line_up()
        elif key == KeyCodes.DELETE:
            index = self.indexes_to.get(self.pos, _UNUSED)
            if index is _UNUSED:
                self.events(UNREACHABLE, self.pos)
                return
            if len(self.value) > self.text_offset + len(self.displayed_value):
                r_index = index + self.text_offset
                value = self.value
                self.value = value[:r_index] + value[r_index + 1:]
            else:
                try:
                    self.lines.del_(index, False)
                except JoinLines as join:
                    self.join_lines(join.line)
                self.regen_text()
        elif key == KeyCodes.BACK:
            index = self.indexes_to.get(self.pos, -1)
            if index > 0:
                self.pos = self.get_next_pos_from(self.pos, direction="back")
                index = self.indexes_to.get(self.pos, _UNUSED)
                if index is _UNUSED:
                    self.events(UNREACHABLE, self.pos)
                    return
                index = self.lines.del_(index, True, self.insertion)
                self.pos = self.indexes_from[index]
                self.regen_text()
            elif self.text_offset > 0 and self.text_prefix:
                self.value = self.text_prefix.value[:-1] + self.displayed_value + self.text_postfix.value
            if self.text_past_end:
                new_pos = self.get_next_pos_from(self.pos)
                if new_pos in Rect(self.text.rect):
                    self.pos = new_pos
                    self.text_past_end = False
        elif key == KeyCodes.INSERT:
            self.insertion ^= True
        # TBD: add support for certain control for line editing characters, like ctrl + k, ctrl + j, ctrl + a...

        if key != KeyCodes.ENTER and (key in KeyCodes.codes or ord(key) < 0x20):
            valid_symbol = False

        if valid_symbol:
            index = self.indexes_to.get(self.pos, _UNUSED)
            if index is _UNUSED:
                self.events(UNREACHABLE, self.pos)
                return

            if self.insertion:
                try:
                    index = self.lines.insert(index, key)
                    if index != self.indexes_to[self.pos]:
                        self.pos = self.indexes_from[index]

                except TextDoesNotFit:
                    if not self.larger_than_displayed or len(self.value) >= self.text_size :
                        self.events(OVERFILL)
                    else:
                        if key == KeyCodes.ENTER:
                            if len(self.lines.hard_lines) == 1:
                                return
                            if self.lines.at_last_line(self.pos):
                                line, soft_index = self.lines.get_index_in_soft_line(index)
                                new_pos = self.pos
                                self.scroll_line_up()
                                self.cursor_to_previous_shape_line()
                            else:
                                self.scroll_last_line_down()
                            return self.change(key=key)
                        if self.get_next_pos_from(self.pos) not in self.text.rect and len(self.lines.hard_lines) > 1:
                            self.scroll_line_up()
                            self.cursor_to_previous_shape_line()
                            new_pos = self.get_next_pos_from(self.pos)
                            if new_pos in self.text.rect:
                                self.pos = new_pos
                            return self.change(key=key)

                        value = self.value
                        new_text = value[:self.text_offset + index] + key + value[self.text_offset + index:]
                        try:
                            self.value = new_text
                        except TextDoesNotFit:
                            self.events(OVERFILL)
            else:
                # WIP: take in account text_size here
                index = self.lines.set(index, key)

            #if key != KeyCodes.ENTER:
            if key not in (KeyCodes.ENTER, '\n'):
                new_pos = self.get_next_pos_from(self.pos)
                if new_pos in self.text.rect:
                    self.pos = new_pos
                    self.text_past_end = False
                else:
                    if self.larger_than_displayed and len(self.value) < self.text_size:
                        if len(self.lines.hard_lines) > 1:
                            self.scroll_line_up()
                            self.cursor_to_previous_shape_line()
                            new_pos = self.get_next_pos_from(self.pos)
                            if new_pos in self.text.rect:
                                self.pos = new_pos
                        else:
                            self.scroll_char_left()
                    else:
                        self.text_past_end = True

            self.regen_text()


    def regen_text(self):
        self.text.writtings.clear()
        with self.text.recording as text_data:
            self.text.at(self.initial_pos, escape(self.raw_value))
        self.last_text_data = text_data

    def kill(self):
        self.focus = False

    def events(self, type, *args):
        terminedia.events.Event(terminedia.events.Custom, subtype=type, owner=self, info=args)

    def clear(self):
        self.value = ""
        self.pos = self.initial_pos


class Text(Widget):

    def __init__(self, parent, size=None, label="", value="", *, pos=(0,0), text_plane=1, sprite=None, border=None, click_callback=(), text_size=None, cursor_pos=None, **kwargs):
        """Multiline text-editing Widget

        (roughly the same role as HTML's "textarea" form input).
        Creates a new sprite attached to parent, and, when focused, display an emulated cursor,
        which captures all key-presses and composes text, allowing free movement
        with arrow-keys.

        Use the ".value" property to retrieve typed-in contents.

        Args:
            - parent (Union[Screen, Shape, Sprite]: container where the widget is to be added as a sprite
            - size (V2): Widget size in cell positions. Defaults to parent text-size at the choosen text-resolution
            - label (str): Widget label [TBD]
            - value (str): initial text contents
            - pos (V2): where on parent to draw the widget
            - text_plane (Union(int, str)): which text-plane from Sprite to build the widget in (1, 4, 6, 8, ...)
            - sprite (Optional[Sprite]): pre-created sprite which will serve as the widget itself.
                Do not pass "size" if sprite is given. Can be used custom-prepared :any:`TextPlane` with
                Marks pre-set, including direction-changing and teleporting Marks. The widget
                is capable of editing text with arbitrary text-flows composed by custom Marks.
            - border (Bool): whether to draw a border around the widget rectangle. Border size is in addition
                to given size.
            - click_callback (callable): callback for a mouse-click event
            - text_size (int): [WIP] Maximum text size that should be allowed to be typed in. By default "None",
                meaning the maximum value is size.x * size.y characters.
            - **kwargs: arguments passed unfiltered to : any:Widget base class.

        """

        click_callbacks = [self.click]
        _ensure_extend(click_callbacks, click_callback)
        if border:
            if size:
                sprite = self._sprite_from_text_size(size, text_plane, pos=pos, padding=(2,2))
                size = None
            if not isinstance(border, Transformer):
                border = terminedia.transformers.library.box_transformers["LIGHT_ARC"]
            self.has_border = 1
            text = sprite.shape.text[text_plane]
            text.add_border(border)
            # del text
        super().__init__(parent, size, pos=pos, text_plane=text_plane, sprite=sprite,
                         keypress_callback=self.__class__.handle_key, click_callback=click_callbacks,
                         **kwargs)
        text = self.sprite.shape.text[self.text_plane]

        self.editable = Editable(text, parent=self, value=value, text_size=text_size, pos=cursor_pos)

    def get(self):
        return self.editable.value

    def kill(self):
        self.editable.kill()
        super().kill()

    def handle_key(self, event):
        errored = False
        try:
            self.editable.change(event)
        except Exception as exc:
            errored = True
            if terminedia.DEBUG:
                raise
        finally:
            # do not allow keypress to be processed further
            if not errored:
                raise EventSuppressFurtherProcessing()

    def click(self, event):
        self.editable.pos = ((event.pos - (self.editable.text.pad_left, self.editable.text.pad_top)) / (self.editable.text.char_size)).as_int

    @property
    def value(self):
        return self.editable.value

    @value.setter
    def value(self, text):
        self.editable.value = text

    def clear(self):
        self.editable.clear()



class Entry(Text):
    def __init__(self, parent, width, label="", value="", *, enter_callback=None, pos=(0, 0), text_plane=1, **kwargs):
        super().__init__(parent, (width, 1), label=label, value=value, pos=pos, text_plane=text_plane, enter_callback=enter_callback, **kwargs)
        self.done = False

    def _default_enter(self, event):
        self.done = True

    @Text.value.setter
    def value(self, text):
        text = text.replace("\n", "\\n")
        Text.value.__set__(self, text)
