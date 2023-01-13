from collections import namedtuple
from copy import deepcopy
import itertools
from math import ceil

import terminedia

from terminedia import Mark, Transformer

from terminedia import V2, Rect

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

MarkCell = namedtuple("MarkCell", "from_pos to_pos flow_changed is_used direction")
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
    last_cell = MarkCell(None, pos, False, True, direction)
    from_map = {pos: [last_cell] }
    to_map = {None: [last_cell] }
    rect = terminedia.Rect((0, 0), text.size)
    counter = 0
    marks = _ensure_sequence(text.marks.abs_get(pos, _EMPTY_MARK,))
    while True:
        prev_pos = pos

        pos, direction, flow_changed, position_is_used = text.marks.move_along_marks(prev_pos, direction)

        cell = MarkCell(prev_pos, pos, flow_changed, position_is_used, direction)
        from_map.setdefault(pos, []).append(cell)
        to_map.setdefault(prev_pos, []).append(cell)

        counter += 1
        marks = _ensure_sequence(text.marks.abs_get(pos, _EMPTY_MARK,))
        if marks[0] is _EMPTY_MARK and pos not in rect or counter > 3 * rect.area:
            # we can have a text flow that goes through each position more than once,
            # but we have to halt it at some point - hence the "3 *" above.
            break

    return to_map, from_map


class TextDoesNotFit(ValueError): #sentinel
     pass


lcache = ClassCache()

class Lines:
    # helper class closely tied to Editable
    def __init__(self, value, parent):
        self.parent= parent
        self.reload(value)
        self._last_event = (None, None, None, None)

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

    def reload(self, value):
        if isinstance(value, str):
            value = value.split("\n")
        if len(value) < self.len_hard_lines:
            value.extend([""] * (self.len_hard_lines - len(value) - 1))
        self.soft_lines = value

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

    @lcache.invalidate
    def _set(self, hard_index, value, insert):
        prev = deepcopy(self.soft_lines)

        line, index =(self.get_index_in_soft_line(hard_index))
        dist_from_eol = index - len(self.soft_lines[line])
        if value == KeyCodes.ENTER:
            if insert:
                if not self.soft_lines[-1]:
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
                    self._last_event[1] == line - 1 and
                    self._last_event[2] == len(self.soft_lines[line - 1]) - 1 and
                    self._last_event[3] == self.parent.tick - 1
                ):
                    line -= 1
                    index = self.soft_lines[line]

            # this is the same in insertion mode and setting mode
            # but when we hit a hard-line boundary there is more stuff to be done
            self.soft_lines[line] += value
            if self._soft_line_exceeded_space(line):
                if insert:
                    if not self.soft_lines[-1]:
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
            if not self.soft_lines[-1]:
                self.soft_lines.pop()
                self.soft_lines_spams.pop()
            self.soft_lines_spams[line] += 1

        try:
            self._hard_load_from_soft_lines()
        except TextDoesNotFit:
            self.soft_lines = prev
            self._hard_load_from_soft_lines()
            raise
        self._last_event = (hard_index, line, index, self.parent.tick)
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
        elif backspace and insert:
            self.soft_lines[line] = self.soft_lines[line][:-1]
            hard_index -= dist_from_eol

        if backspace:
            hard_index -= 1
        try:
            self._hard_load_from_soft_lines()
        except TextDoesNotFit:
            pass
        self._last_event = (None, None, None, None)

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

        if parent:
            self.parent.sprite.transformers.append(CursorTransformer(self))
        self.last_rendered_cursor = None
        self.last_text_data = []
        self.text_pathto_map, self.text_path_map = map_text(self.text, self.initial_pos, self.context.direction)

        self.impossible_pos = False


        # properties used to edit text larger than the display-size:
        self.display_size = len(self.text_path_map) - 1
        if text_size is None:
            text_size = self.display_size - 1
        self.text_size = text_size

        self.text_offset = offset

        # resume building initial internal-state
        self._build_shape_indexes()
        self.lines = Lines(value, self)
        self.tick = 0
        self.text_size = text_size
        # state to indicate if insertion point at last cell
        # should be _after_ or _before_ last character
        self.text_past_end = False

        self.value = value

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
        index = self.indexes_to.get(self.pos, _UNUSED)
        if index is _UNUSED:
            return False
        line, soft_index = self.lines.get_index_in_soft_line(index)
        if line == 0:
            return False
        cells = self.cells_at_lines[line - 1]
        line_len = len(cells) - 1
        self.pos = cells[min(line_len, soft_index)]
        return True

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
            return self.text_prefix + self.displayed_value + empty_lines + self.text_postfix
        else:
            return self.displayed_value

    @value.setter
    def value(self, text):
        off = self.text_offset
        ds = self.display_size
        pre, editable, post = text[:off], text[off:off + ds], text[off + ds:]
        if editable.count("\n") >= len(self.lines.hard_lines):
            max_lines = len(self.lines.hard_lines)
            editable_lines = editable.split("\n")
            editable = "\n".join(editable_lines[:max_lines])
            post = "\n" + "\n".join(editable_lines[max_lines:]) + post
        self.text_prefix = pre
        self.text_postfix = post
        self.lines.reload(editable)
        self.lines._hard_load_from_soft_lines()
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
        text = self.value
        self.text_offset += 1
        self.value = text

    def scroll_char_left(self):
        text = self.value
        self.text_offset -= 1
        self.value = text

    def scroll_line_up(self):
        # scroll lines up
        lines = self.value.split("\n", 1)
        text = self.value
        self.text_offset += min(len(lines[0]) + 1, len(self.lines.hard_lines[0]))
        self.value = text

    def scroll_last_line_down(self):
        last_line = self.lines.soft_lines.pop()
        self.text_postfix = f"\n{last_line}" + self.text_postfix
        self.lines.soft_lines.append('')
        self.lines._hard_load_from_soft_lines()
        self.regen_text()

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
                elif index < len(self.indexes_from) - 2:
                    new_pos = self.indexes_from[index + 1]
                    if new_pos in self.text.rect:
                        self.pos = new_pos
                elif len(self.value) > self.text_offset + len(self.displayed_value):
                    self.scroll_char_right()
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
                    self.scroll_char_left()

            if key == KeyCodes.UP and self.pos.y > 0:
                self.pos = self.text.extents(self.pos, " ", direction="up")
            elif key == KeyCodes.DOWN and self.pos.y < self.text.size.y - 1:
                self.pos = self.text.extents(self.pos, " ", direction="down")
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
                self.lines.del_(index, False)
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
            elif self.text_offset > 0:
                pre, displayed, post = self.text_prefix, self.displayed_value, self.text_postfix
                self.text_offset -= 1
                self.value = pre[:-1] + displayed + post
            self.regen_text()
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
                    if len(self.value) >= self.text_size:
                        self.events(OVERFILL)
                    else:
                        if key == KeyCodes.ENTER:
                            if len(self.lines.soft_lines) == 1:
                                return
                            if self.lines.at_last_line(self.pos):
                                line, soft_index = self.lines.get_index_in_soft_line(index)
                                new_pos = self.pos
                                self.scroll_line_up()
                                self.cursor_to_previous_shape_line()
                            else:
                                self.scroll_last_line_down()
                            return self.change(key=key)
                            # key = "\n"
                        # if at last visible_position:
                        if self.get_next_pos_from(self.pos) not in self.text.rect:
                            if self.text_offset + index <= len(self.value) - 1:
                                if self.text_past_end:
                                    self.text_offset += 1
                                else:
                                    self.text_past_end = True
                        value = self.value
                        new_text = value[: self.text_offset + index] + key + value[self.text_offset + index:]
                        self.value = new_text

            else:
                # WIP: take in account text_size here
                index = self.lines.set(index, key)

            #if key != KeyCodes.ENTER:
            if key not in (KeyCodes.ENTER, '\n'):
                new_pos = self.get_next_pos_from(self.pos)
                if new_pos in Rect(self.text.rect):
                    self.pos = new_pos
                    self.text_past_end = False
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

        try:
            self.editable.change(event)
        finally:
            # do not allow keypress to be processed further
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
