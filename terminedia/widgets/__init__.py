import enum
from collections import namedtuple
from collections.abc import Iterable, Mapping
from copy import deepcopy
from inspect import isawaitable
from math import ceil

import terminedia

from terminedia import shape, Mark, Transformer, Directions

from terminedia.sprites import Sprite
from terminedia.utils import contextkwords
from terminedia import events, V2, Rect

from terminedia.events import EventSuppressFurtherProcessing
from terminedia.input import KeyCodes
from terminedia.utils import ClassCache
from terminedia.utils.gradient import RangeMap
from terminedia.text import escape, plane_names
from terminedia.text.planes import relative_char_size
from terminedia.text.style import MLTokenizer
from terminedia.values import RETAIN_POS
from terminedia.values import RelativeMarkIndex


###############
#
# Transformers, Sentinels and Helpers
#
##############


class WidgetEvents:
    OVERFILL = "OVERFILL"
    UNREACHABLE = "UNREACHABLE"

OVERFILL = WidgetEvents.OVERFILL
UNREACHABLE = WidgetEvents.UNREACHABLE


_NOT_FOUND = object()
_EMPTY_MARK = Mark()
_UNUSED = "*"
_USED = " "
_ENTER = "#"

MarkCell = namedtuple("MarkCell", "from_pos to_pos flow_changed is_used direction")
BackTrack = namedtuple("BackTrack", "position direction distance_to_closest_mark mark_count")


class WidgetCancelled(Exception):
    pass


class CursorTransformer(terminedia.Transformer):
    blink_cycle = 5

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
        if not self.parent.parent.focus or not tick % self.blink_cycle:
            return value
        size = self.parent.text.char_size
        pos -= (self.parent.text.pad_left, self.parent.text.pad_top)
        if size == (1,1):
            if pos != self.parent.pos:
                return value
        else:
            rect = Rect(self.parent.pos * size, width_height = size)
            if pos not in rect :
                return value
        return (value if isinstance(value, terminedia.Effects) else 0)| self.effect_table[self.parent.insertion]


    #def background(self, value, pos, tick):
        #if not self.parent.focus or pos != self.parent.pos or not tick % 7:
            #return value
        #return (127, 127, 0)
        #return (value if isinstance(value, terminedia.Effects) else 0)| self.effect


class SelectorTransformer(terminedia.Transformer):

    def __init__(self, parent, effect="reverse"):
        self.parent = parent
        self.effect = terminedia.Effects(effect)

        super().__init__()

    def effects(self, value, pos, tick):
        size = self.parent.text.char_size
        row = self.parent.selected_row
        if size == (1,1):
            if pos[1] != row + self.parent.has_border:
                return value
        else:
            row_size = size[1]
            size1_row = row * row_size + self.parent.has_border
            if not(size1_row <= pos[1] < size1_row + row_size):
                return value
        if self.parent.has_border and (pos[0] == 0 or pos[0] == self.parent.shape.width - 1):
            return value
        return self.effect


class FocusTransformer(terminedia.Transformer):

    bg_color = terminedia.Color((.3, .3, .3))

    def background(self, source, background, pos):
        if not (pos[0] in (0, source.size[0] - 1) or pos[1] in (0, source.size[1] - 1)):
            return background
        return self.bg_color
        #if background is terminedia.DEFAULT_BG:
            #background = self.bg_color


def _ensure_sequence(mark):
    return [mark,] if isinstance(mark, Mark) else mark


def _ensure_extend(seq, value):
    if isinstance(value, Iterable):
        seq.extend(value)
    elif value is not None:
        seq.append(value)


###############
#
# Text Editing Guts
#
##############

def map_text(text, pos, direction):
    """Given a text plane, maps out the way that each reachable cell can be acessed

    The map re-interprets the Marks that affect text flow found on the text plan -
    but Marks with "special_index" and other kind of dynamic marks will likely
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
        self._reload(value)
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

    def _reload(self, value):
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
        hard_line_index = self.soft_line_map[line]
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

        prev = deepcopy(self.soft_lines)

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


class Editable:
    """Internal class to widgets -
    responsible for managing a keyboard-event-echo-in-text-plane
    pattern. Use text-editing subclasses of Widget instead of this.

    You may re-initialize the widget.editable instance if you make layout changes
    to the underlying shape (text-flow Marks) after the widget is instantiated.
    """
    def __init__(self, text_plane, parent=None, value="", pos=None, line_sep="\n"):
        self.focus = True
        self.initial_pos = self.pos = pos or V2(0, 0)
        self.text = text_plane
        self.parent = parent
        self.line_sep = line_sep
        #self.enter_callback = enter_callback
        #self.esc_callback = esc_callback
        self.insertion = True
        self.context = self.text.owner.context
        self.initial_direction = self.context.direction

        if parent:
            self.parent.sprite.transformers.append(CursorTransformer(self))
        self.last_rendered_cursor = None
        self.last_text_data = []
        self.text_pathto_map, self.text_path_map = map_text(self.text, self.initial_pos, self.context.direction)

        self.impossible_pos = False

        self.build_value_indexes()
        self.lines = Lines(value, self)
        self.tick = 0

    def build_value_indexes(self):
        pos = self.initial_pos
        indexes_to = {}
        indexes_from = {}
        new_line_indices = [0]
        count = 0
        index_counted = False
        while True:
            indexes_from[count] = pos
            indexes_to[pos] = count
            count += 1
            try:
                cell = self.text_pathto_map[pos][0]
            except KeyError:
                break
            if cell.flow_changed: #not cell.is_used:
                new_line_indices.append(count)
                index_counted = True
            else:
                index_counted = False
            pos = cell.to_pos
        if not index_counted:
            new_line_indices.append(count - 1)
        self.raw_value = " " * len(indexes_from)
        self.line_indexes = RangeMap(new_line_indices)
        self.indexes_from = indexes_from
        self.indexes_to = indexes_to

    @property
    def text_space(self):
        return len(self.indexes_from) - 1

    def get_next_pos_from(self, pos, direction="forward"):
        if direction == "forward":
            return self.text_pathto_map[pos][0].to_pos
        return self.text_path_map[pos][0].to_pos

    @property
    def value(self):
        return "\n".join(self.lines.soft_lines)
        #return ''.join(c.char for c in self.raw_value if c.mask is not _UNUSED)

    @property
    def shaped_value(self):
        return self.raw_value

    def keypress(self, event):
        try:
            self.change(event)
        finally:
            # do not allow keypress to be processed further
            raise EventSuppressFurtherProcessing()

    def change(self, event):
        """Called on each keypress when the widget is active. Take 2"""

        self.tick += 1

        #if event.key == KeyCodes.ENTER and self.enter_callback:
            #self.enter_callback(self)
        #if event.key == KeyCodes.ESC and self.esc_callback:
            #self.esc_callback(self)

        key = event.key
        valid_symbol = True

        if key in (KeyCodes.UP, KeyCodes.DOWN, KeyCodes.LEFT, KeyCodes.RIGHT):
            if key == KeyCodes.RIGHT and self.pos.x < self.text.size.x - 1:
                self.pos = self.text.extents(self.pos, " ", direction="right")
            if key == KeyCodes.LEFT and self.pos.x > 0:
                self.pos = self.text.extents(self.pos, " ", direction="left")
            if key == KeyCodes.UP and self.pos.y > 0:
                self.pos = self.text.extents(self.pos, " ", direction="up")
            elif key == KeyCodes.DOWN and self.pos.y < self.text.size.y - 1:
                self.pos = self.text.extents(self.pos, " ", direction="down")
        elif key == KeyCodes.DELETE:
            index = self.indexes_to.get(self.pos, _UNUSED)
            if index is _UNUSED:
                self.events(UNREACHABLE, self.pos)
                return
            self.lines.del_(index, False)
            self.regen_text()
        elif key == KeyCodes.BACK and self.indexes_to.get(self.pos, -1) > 0:
            self.pos = self.get_next_pos_from(self.pos, direction="back")
            index = self.indexes_to.get(self.pos, _UNUSED)
            if index is _UNUSED:
                self.events(UNREACHABLE, self.pos)
                return
            index = self.lines.del_(index, True, self.insertion)
            self.pos = self.indexes_from[index]

            self.regen_text()
        elif key == KeyCodes.INSERT:
            self.insertion ^= True
        # TBD: add support for certain control for line editing characters, like ctrl + k, ctrl + j, ctrl + a...


        if key is not KeyCodes.ENTER and (key in KeyCodes.codes or ord(key) < 0x1b):
            valid_symbol = False


        if valid_symbol:
            index = self.indexes_to.get(self.pos, _UNUSED)
            if index is _UNUSED:
                self.events(UNREACHABLE, self.pos)
                return

            if self.insertion:
                try:
                    index = self.lines.insert(index, key)
                except TextDoesNotFit:
                    self.events(OVERFILL)
                    return
            else:
                index = self.lines.set(index, key)
            self.pos = self.indexes_from[index]
            if key != KeyCodes.ENTER:
                self.pos = self.get_next_pos_from(self.pos)

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


###############
#
# Widgets Coordination Machinery
#
##############



class WidgetEventReactor:
    def __init__(self):
        self.registry = {}
        self.focus = None
        self.main_mouse_subscription = events._SystemSubscription(events.MouseClick, self.screen_click)
        self.main_mouse_subscription = events._SystemSubscription(events.MouseDoubleClick, self.screen_double_click)
        self.focus_order = []
        self.last_focused_index = 0

    def __delitem__(self, widget):
        del self.registry[widget]
        while widget in self.focus_order:
            self.focus_order.remove(widget)

    def register(self, widget):
        #self.rect_registry[widget.sprite.absrect] = widget
        self.registry[widget] = widget.sprite
        self.focus = widget
        self.focus_order.append(widget)

    def move_to_focus_position(self, widget, position):
        while widget in self.focus_order:
            self.focus_order.remove(widget)
        self.focus_order.insert(position, widget)

    def screen_click(self, event):
        return self.inner_click(event, "click_callbacks")

    def screen_double_click(self, event):
        return self.inner_click(event, "double_click_callbacks")

    def inner_click(self, event, callback_type):
        for widget, sprite in self.registry.items():
            if not widget.active:
                continue
            rect = sprite.absrect
            if event.pos in rect:
                callbacks = getattr(widget, callback_type, None)
                if callbacks:
                    local_event = event.copy(pos=event.pos - rect.c1)
                    local_event.widget = widget
                    for callback in reversed(callbacks):
                        try:
                            callback(local_event)
                        except EventSuppressFurtherProcessing:
                            break
                # FIXME: not quite right. maybe check all hitted sprites first, then execute callbacks in reverse "z-order"
                if not isinstance(widget, Container):
                    raise EventSuppressFurtherProcessing()

    @property
    def focus(self):
        return self._focus

    @focus.setter
    def focus(self, widget):
        prev = self._focus if "_focus" in self.__dict__ else None
        if prev and prev is not widget:
            prev.focus = False
        self._focus = widget

    def _tab_change_focus(self, widget, op):
        if not self.focus_order:
            return
        try:
            index = self.focus_order.index(widget)
        except ValueError:
            index = self.last_focused_index
        index = op(index) % len(self.focus_order)
        self.focus_order[index].focus = True
        self.last_focused_index = index

    def focus_next(self, widget):
        return self._tab_change_focus(widget, lambda i: i + 1)

    def focus_previous(self, widget):
        return self._tab_change_focus(widget, lambda i: i - 1)


# singleton
WidgetEventReactor = WidgetEventReactor()


###############
#
# Base Widgets
#
##############


class Widget:

    def __init__(
        self, parent, size=None, pos=(0,0), text_plane=1, sprite=None, *,
        click_callback=None, esc_callback=None, enter_callback=None,
        keypress_callback=None, double_click_callback=None, tab_callback=None,
        cancellable=False, focus_position = ..., focus_transformer = None,
        context=None
    ):
        """Widget base

        Under development. More docs added as examples/functionality is written.

        By default, an widget looses focus when "ESC" is pressed.
        if "cancellable" is True, this will kill the widget and raise a WidgetCancelled execption.

        To avoid cancelation, pass an "esc_callback" which raises an EventSuppressFurtherProcessing.
        """
        self.infocus = False
        original_parent = parent
        if isinstance(parent, (terminedia.Screen, Widget)):
            parent = parent.shape

        self.cancellable = cancellable
        if not any((size, sprite)):
            raise TypeError("Either a size or a sprite should be given for a widget")
        if sprite and size:
            raise TypeError("If a sprite is given, widget size if picked from the sprite's shape")

        text_plane = plane_names[text_plane]
        if not sprite:
            self.sprite = self._sprite_from_text_size(size, text_plane, pos)
        else:
            self.sprite = sprite
            size = sprite.shape.text[text_plane].size
        self.shape = self.sprite.shape
        if context:
            self.shape.context = context
        # initialize size property without triggering events
        self._set_size(self.shape.size)

        self.parent = parent
        self.click_callbacks = [self._default_click]
        _ensure_extend(self.click_callbacks, click_callback)


        self.double_click_callbacks = []
        if double_click_callback:
            _ensure_extend(self.double_click_callbacks, double_click_callback)

        self.esc_callbacks = [self.__class__._default_escape]
        _ensure_extend(self.esc_callbacks, esc_callback)

        self.enter_callbacks = [self.__class__._default_enter]
        _ensure_extend(self.enter_callbacks, enter_callback)

        self.tab_callbacks = [self.__class__._default_tab]
        _ensure_extend(self.tab_callbacks, tab_callback)

        self.keypress_callbacks = []
        _ensure_extend(self.keypress_callbacks, keypress_callback)

        self.text_plane = text_plane
        if sprite not in parent.sprites:
            parent.sprites.append(self.sprite)

        self.subscriptions = [events.Subscription(events.KeyPress, self.keypress, guard=lambda e: self.focus)]
        self.terminated = False

        if focus_transformer is not None:
            self.focus_transformer = focus_transformer
        else:
            self.focus_transformer = self.__class__.focus_transformer()

        WidgetEventReactor.register(self)

        if focus_position is not ...:
            self.move_to_focus_position(focus_position)

        if hasattr(original_parent, "register_child"):
            original_parent.register_child(self)

        # trigger resizing event:
        self.size = self.size

    focus_transformer = FocusTransformer

    def move_to_focus_position(self, focus_position):
        """Set the 'tab-stop' order of this widget. (html equivalent "tab-index")

        if focus_position is None, the widget is changed to be unreachable by <tab>
        """
        if focus_position is None:
            WidgetEventReactor.focus_order.remove(self)
            return
        WidgetEventReactor.move_to_focus_position(self, focus_position)

    def _default_click(self, event):
        if not self.focus:
            self.focus = True

    @property
    def active(self):
        return self.sprite.active

    @property
    def focus(self):
        return WidgetEventReactor.focus is self

    @focus.setter
    def focus(self, value):
        if value:
            WidgetEventReactor.focus = self
            if hasattr(self, "subs"):
                self.subs.prioritize()
            self.sprite.transformers.append(self.focus_transformer)
        else:
            if WidgetEventReactor.focus is self:
                WidgetEventReactor._focus = None
            if self.focus_transformer in self.sprite.transformers:
                self.sprite.transformers.remove(self.focus_transformer)

    def kill(self):
        self.sprite.kill()
        try:
            del WidgetEventReactor[self]
        except KeyError:
            pass
        self.focus = False
        self.done = True
        if getattr(self, "subscriptions", None):
            for subs in self.subscriptions:
                if not subs.terminated:
                    subs.kill()
            self.subscriptions.clear()
        self.terminated = True

    def _default_escape(self, event):
        if self.cancellable:
            self.kill()
            self.cancelled = True
        self.focus = False

    def _default_enter(self, event):
        pass

    def _default_tab(self, event):
        if event.key == KeyCodes.TAB:
            WidgetEventReactor.focus_next(self)
        else: # shit+tab
            WidgetEventReactor.focus_previous(self)

    def keypress(self, event):
        key = event.key
        for target_key, callback_list in (
            (KeyCodes.ENTER, self.enter_callbacks),
            (KeyCodes.ESC, self.esc_callbacks),
            (KeyCodes.TAB, self.tab_callbacks),
            (KeyCodes.SHIFT_TAB, self.tab_callbacks),
            ("all", self.keypress_callbacks)
        ):
            if key == target_key or target_key=="all" and callback_list:
                for callback in reversed(callback_list):
                    try:
                        callback(self, event)
                    except EventSuppressFurtherProcessing:
                        if target_key == "all":
                            raise
                        break

    def _sprite_from_text_size(self, text_size, text_plane, pos, padding=(0,0)):
        text_size = V2(text_size)
        text_plane = plane_names[text_plane]
        size = text_size * (ceil(1/relative_char_size[text_plane][0]), ceil(1/relative_char_size[text_plane][1]))
        shape = terminedia.shape(size + padding)
        sprite =Sprite(shape)
        sprite.pos = pos
        return sprite

    def _set_size(self, value):
        # set initial size, used by init in a way not to trigger shape-resize
        self.__dict__["size"] = value

    @property
    def size(self):
        return self.__dict__["size"]

    @size.setter
    def size(self, new_size):
        old_size = self.__dict__.get("size", V2(0,0))
        if new_size != old_size:
            self.shape.resize(new_size)
            self.__dict__["size"] = new_size
        events.Event(events.WidgetResize, widget=self, new_size=new_size, old_size=old_size)


    def __await__(self):
        """Before awaiting: not all widgets have a default condition to be considered 'done':
        A custom callback must set widget.done=True, or the widget might await forever.
        """
        while not getattr(self, "done", False):
            yield None
        if not self.terminated:
            self.kill()
        if getattr(self, "cancelled", False):
            raise WidgetCancelled()
        return getattr(self, "value", None)


class Text(Widget):


    def __init__(self, parent, size=None, label="", value="", pos=(0,0), text_plane=1, sprite=None, border=None, click_callback=(), **kwargs):

        click_callbacks = [self.click]
        _ensure_extend(click_callbacks, click_callback)
        if border:
            if size:
                sprite = self._sprite_from_text_size(size, text_plane, pos=pos, padding=(2, 2))
                size = None
            if not isinstance(border, Transformer):
                border = terminedia.transformers.library.box_transformers["LIGHT_ARC"]
            self.has_border = 1
        super().__init__(parent, size, pos=pos, text_plane=text_plane, sprite=sprite,
                         keypress_callback=self.__class__.handle_key, click_callback=click_callbacks,
                         **kwargs)
        text = self.sprite.shape.text[self.text_plane]
        if border:
            text.add_border(border)

        self.editable = Editable(text, parent=self, value=value)

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


class Entry(Text):
    def __init__(self, parent, width, label="", value="", enter_callback=None, pos=(0, 0), text_plane=1, **kwargs):
        super().__init__(parent, (width, 1), label=label, value=value, pos=pos, text_plane=text_plane, enter_callback=enter_callback, **kwargs)
        self.done = False

    def _default_enter(self, event):
        self.done = True


class Button(Widget):
    def __init__(self, parent, text="", command=None, pos=(0, 0), text_plane=1, padding=0, y_padding=None, sprite=None, border=None, **kwargs):
        if not command and "click_callback" in kwargs:
            command = kwargs.pop("click_callback")
        if y_padding is None:
            y_padding = padding
        if not sprite:
            size = len(text) + padding * 2 + 1, 1 + y_padding * 2

        self.text_line = y_padding

        if command:
            enter_callback = lambda widget, event: command(event)
        else:
            enter_callback = None

        if border:
            if size:
                sprite = self._sprite_from_text_size(size, text_plane, pos=pos, padding=(2, 2))
                size = None
            if not isinstance(border, Transformer):
                border = terminedia.transformers.library.box_transformers["LIGHT_ARC"]
            self.has_border = 1

        super().__init__(parent, size, pos=pos, text_plane=text_plane,
                         sprite=sprite, click_callback=command, enter_callback=enter_callback, **kwargs)
        self.border = border
        self.text = text

        # if not sprite and text:
        #    self.shape.text[self.text_plane][padding - 1 if border else 0, y_padding - 1 if border else 0] = text

    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, value):
        # TODO: resize shape
        self._text = value
        text_plane = self.shape.text[self.text_plane]

        self.shape.clear()
        text_plane.clear()
        text_plane[0, self.text_line] = f"{value:^{text_plane.size.x}s}"
        if self.border:
            text_plane.add_border(self.border)


Label = Button


_selector_option = namedtuple("option", "raw_text value parsed_text")


class Selector(Widget):
    def __init__(
        self, parent, options, *,
        callback=None, pos=None, text_plane=1, sprite=None,
        border=None, align="center",
        selected_row=0, offset=0, click_callback=None,
        min_height=1, max_height=None,
        min_width=1, max_width=100,
        **kwargs
    ):
        if isinstance(options, dict):
            str_options = list(options.keys())
            options_values = list(options.values())
        else:
            str_options = [opt[0] if isinstance(opt, tuple) else opt for opt in options]
            options_values = [(opt[1] if isinstance(opt, tuple) else opt) for str_opt, opt in zip(str_options, options) ]

        self.min_height = min_height
        self.max_height = max_height or parent.size.y
        self.min_width = min_width
        self.max_width = max_width

        self.options = [_selector_option(opt, val, self._stripped_opt(opt)) for opt, val in zip(str_options, options_values)]
        self.__dict__["offset"] = min(offset, len(self.options) - 1)

        self.align = align
        self.has_border = 0
        if border:
            if not isinstance(border, Transformer):
                border = terminedia.transformers.library.box_transformers["LIGHT_ARC"]
            self.has_border = 1

        click_callbacks = [self._select_click]
        _ensure_extend(click_callbacks, click_callback)
        super().__init__(parent, self.size, pos=pos, text_plane=text_plane, sprite=sprite, click_callback=click_callbacks, keypress_callback=self.__class__.change, double_click_callback=self._select_double_click, **kwargs)
        self.border = border
        self.text = self.shape.text[self.text_plane]
        if self.has_border:
            self.text.add_border(border)

        self.redraw()

        self.selected_row = selected_row
        self.str_options = str_options
        self.selected_row = selected_row
        self.transformer = SelectorTransformer(self)
        self.callback = callback

        self.sprite.transformers.append(self.transformer)

    def _stripped_opt(self, raw_opt):
        if isinstance(raw_opt, terminedia.Color):
            opt_text = " " * self.min_width
        else: # str
            tmp = MLTokenizer(raw_opt)
            tmp.parse()
            opt_text = tmp.parsed_text
        return opt_text

    @property
    def _align(self):
        return {"right": ">", "left": "<", "center": "^"}.get(self.align.lower(), self.align)

    @property
    def max_option_width(self):
        # TODO: strip tokens for width calculation
        widths = [len(opt.parsed_text) for opt in self.options if isinstance(opt.raw_text, str)]
        if widths:
            width = max(widths)
        else:
            width = self.min_width
        return width

    @property
    def size(self):
        size = V2(
            max(min(self.max_option_width, self.max_width), self.min_width),
            max(self.min_height,  min(len(self.options), self.max_height))
        )
        if self.has_border:
            size += V2(2,2)
        return size

    @size.setter
    def size(self, value):
        pass #dynamically calculated. Method needs to exist because parnt class tries to set attribute.

    def redraw(self):
        self.text.clear()
        self.shape.clear()
        if self.border:
            self.text.draw_border(transform=self.border)
        for row, opt in enumerate(self.options[self.offset:]):
            if isinstance(opt.raw_text, str):
                # TODO: strip tokens from opt before calculating aligment
                tmp = f"{opt.parsed_text:{self._align}{self.text.size.x}s}"
                tmp = tmp.replace(opt.parsed_text, opt.raw_text)
                self.text[0, row] = tmp
            elif isinstance(opt.raw_text, terminedia.Color):
                self.text[0, row] = f"[foreground: {opt.raw_text.html}][background: {opt.raw_text.html}]{' ' * (self.text.size.x - 2):^s}"
        scroll_mark_x = self.text.size.x - 1
        if self.offset > 0:
            self._scroll_mark_up = V2(scroll_mark_x, 0)
            self.text[self._scroll_mark_up] = "[effects: reverse]⏶"
        else:
            self._scroll_mark_up = None
        if self.text.size.y + self.offset < len(self.options):
            self._scroll_mark_down = V2(scroll_mark_x,  self.text.size.y - 1)
            self.text[self._scroll_mark_down] = "[effects: reverse]⏷"
        else:
            self._scroll_mark_down = V2(scroll_mark_x, None)
        self.shape.dirty_set()

    def change(self, event):
        key = event.key
        if key == KeyCodes.UP:
            if self.selected_row > 0:
                self.selected_row -= 1
            elif self.offset > 0:
                self.offset -= 1

        elif key == KeyCodes.DOWN:
            if self.selected_row  + self.offset < len(self.options) - 1 and self.selected_row < self.text.size.y - 1:
                self.selected_row += 1
            elif self.offset + self.text.size.y < len(self.options):
                self.offset += 1

        elif key == KeyCodes.ENTER:
            if self.callback:
                self.callback(self)
            self.done = True
        raise EventSuppressFurtherProcessing()

    def _get_clicked_option(self, event):
        selected_row = self.text.pos_to_text_cell(event.pos).y
        if 0 <= selected_row < len(self.options) - self.offset:
            return selected_row
        return None

    @property
    def offset(self):
        return self.__dict__["offset"]

    @offset.setter
    def offset(self, value):
        if value >= len(self.options):
            value = len(self.options) - 1
        if value < 0:
            value = 0
        self.__dict__["offset"] = value
        self.redraw()

    def _select_click(self, event):
        pos = self.text.pos_to_text_cell(event.pos)
        if pos == self._scroll_mark_up:
            self.offset -= 1
            return

        if pos == self._scroll_mark_down:
            self.offset += 1
            return

        selected_row = self._get_clicked_option(event)
        if selected_row is not None:
            self.selected_row = selected_row

    def _select_double_click(self, event):
        selected_row = self._get_clicked_option(event)
        # there may be "blank" positions in the widget - it should not be finished in this case.
        if selected_row != self.selected_row:
            raise EventSuppressFurtherProcessing()

        if self.callback:
            self.callback(self)
        self.done = True
        # there might be 1 or 2 mouseclicks pending as part of the double-click:
        # removing then so they don't triggr side-effects once the widget is done.
        events.event_nuke(lambda e: e.type == events.MouseClick and e.tick == event.tick)
        raise EventSuppressFurtherProcessing()

    @property
    def value(self):
        return self.options[self.selected_row + self.offset][1]

    def __len__(self):
        return len(self.options)

    def __getitem__(self, index):
        return self.options[index]

    def _prechange(self):
        ṕass

    def _poschange(self):
        pass

    def __setitem__(self, index, value):
        if isinstance(value, str):
            value = _selector_option(value, value, self._stripped_opt(value))
        elif len(value) == 2:
            value = _selector_option(value[0], value[1], self._stripped_opt(value[0]))

        prev_size = self.size
        self.options[index] = value
        if self.size != prev_size:
            self.shape.resize(self.size)
        self.redraw()

    def __delitem__(self, index):
        prev_size = self.size
        del self.options[index]
        if self.size != prev_size:
            self.shape.resize(self.size)
        self.redraw()

    def insert(self, index, value):
        if isinstance(value, str):
            value = _selector_option(value, value, self._stripped_opt(value))
        elif len(value) == 2:
            value = _selector_option(value[0], value[1], self._stripped_opt(value[0]))
        prev_size = self.size
        # import os; os.system("reset");breakpoint()
        self.options.insert(index, value)
        if self.size != prev_size:
            self.shape.resize(self.size)
        self.redraw()


class ScreenMenu(Widget):
    """Designed as a complete-navigation solution for an app

    The main idea is get a multilevel dictionary  mapping
    shortcuts to app actions, or submenus, or simply labels.

    Each key in the dictionary shoul dmap to a two-tuple, where the first
    element is an optional callable action - if given as None, the command is
    ignored and non clickable: other parts of the app should handle that shortcut.
    The second element of the tuple is the description for the action

    If the key maps to a dictionary, that is used as another menu-level.

    The menu visibility is optional toggable  if an action in the current level is the string "toggle":
    shortcuts remain active when the menu is toggled off.

    Example dictionary derived from the one used on the 0th version of terminedia-paint:

        self.global_shortcuts = {
            "<space>": (None, "Paint pixel"),
            "←↑→↓": (None, "Move cursor"),
            "x": (None, "Toggle drawing"),
            "v": (None, "Line to last point"),
            "s": (self.save, "Save"),
            "c": (self.pick_color, "Choose Color"),
            "b": (self.pick_background, "Background Color"),
            "l": (self.pick_character, "Pick Char"),
            "i": (self.insert_image, "Paste Image"),
            "e": ((lambda e: setattr(self, "active_tool", self.tools["erase"])), "Erase"),
            "p": ((lambda e: setattr(self, "active_tool", self.tools["paint"])), "Paint"),
            "h": ("toggle", "Toggle help"),
            "q": (self.quit, "Quit"),
        }


    """
    def __init__(self, parent, mapping, columns=1, width=None, max_col_width=25, context=None, gravity=Directions.DOWN, **kwargs):
        self.mapping = mapping.copy()

        self.width = width or parent.size.x
        self.columns = columns
        self.custom_context = context
        self.max_col_width = max_col_width
        self._shape_cache = {}
        self.sprite = None
        self.gravity = gravity
        self.parent = parent
        self.bread_crumbs = []
        # If a toggle menu display shortcut is on a parent level of a menu,
        # record it so it works on child levels:
        self.toggle_key = None
        self._enabled = True

        self._set_mapping(self.mapping)
        self._set_shape()

        super().__init__(parent, sprite=self.sprite, keypress_callback=self.__class__.handle_key, **kwargs)
            #self.sc.sprites.add(self.help_sprite)

    def _set_mapping(self, mapping):
        self.active_mapping = mapping
        if id(mapping) in self._shape_cache:
            self.sh, self.active_keys, self.toggle_key = self._shape_cache[id(mapping)]
            return

        rows = ceil(len(mapping) // self.columns) + 1
        sh = terminedia.shape((self.width,  rows + 2))
        sh.text[1].add_border(transform=terminedia.borders["DOUBLE"])
        col_width = (sh.size.x - 2) // self.columns
        current_row = 0
        if self.custom_context:
            sh.context = self.custom_context
        else:
            sh.context.foreground = terminedia.DEFAULT_FG
        current_col = 0
        actual_width = min(col_width, self.max_col_width)
        commands = [definition[0] for definition in mapping.values()]
        if self.bread_crumbs and "back" not in commands:
            mapping["<ESC>"] = ("back", "back")
        for shortcut, (callback, text) in mapping.items():

            sh.text[1][current_col * col_width + 1, current_row] = f"[effects: bold|underline]{shortcut}[/effects]{text:>{actual_width - len(shortcut) - 3}s}"
            current_row += 1
            if current_row >= rows:
                current_col += 1
                current_row = 0

        self.active_keys = {}
        for shortcut, definition in mapping.items():
            command = definition[0]
            # support for control-characters as shortcut:
            if len(shortcut) == 2 and shortcut[0] == "^":
                shortcut = chr(ord(shortcut[1].upper()) - ord("@"))
            elif shortcut[0] == "<" and shortcut[-1] == ">" and hasattr(KeyCodes, shortcut[1:-1]):
                shortcut = getattr(KeyCodes, shortcut[1: -1])
            self.active_keys[shortcut] = command
            if command == "toggle":
                self.toggle_key = shortcut

        self._shape_cache[id(mapping)] = sh, self.active_keys, self.toggle_key
        self.sh = sh

    def _set_shape(self):
        if not self.sprite:
            self.sprite = terminedia.Sprite(self.sh, alpha=False)
        else:
            self.sprite.shapes[0] = self.sh
        self.sh.dirty_set()
        sprite = self.sprite
        if self.gravity == Directions.DOWN:
            sprite.pos = (0, self.parent.size.y - sprite.rect.height)
        elif self.gravity == Directions.RIGHT:
            sprite.pos = (self.parent.size.x - sprite.rect.width, 0)
        elif self.gravity == Directions.UP or self.gravity == Directions.LEFT:
            sprite.pos = (0, 0)

    def handle_key(self, event):
        if not self._enabled:
            return
        key = event.key
        if key in self.active_keys:
            command = self.active_keys[key]
            if callable(command):
                result = command()
                if isawaitable(result):
                    events._event_process_handle_coro(result)
                raise EventSuppressFurtherProcessing()
            elif command == "toggle":
                self.visible = not self.visible
                raise EventSuppressFurtherProcessing()
            elif command == "back" and self.bread_crumbs:
                self._set_mapping(self.bread_crumbs.pop())
                self._set_shape()
                raise EventSuppressFurtherProcessing()
            elif isinstance(command, Mapping):
                self.bread_crumbs.append(self.active_mapping)
                self._set_mapping(command)
                self._set_shape()
            elif command == None:
                pass # Allow key to be further processed
        elif key == self.toggle_key:
            self.active = not self.active
            raise EventSuppressFurtherProcessing()

    @property
    def visible(self):
        """Toggle widget display - keeping it active"""
        return self.sprite.active

    @visible.setter
    def visible(self, value: bool):
        self.sprite.active = value

    @property
    def enabled(self):
        """setting to False will hide widget and stop key processing"""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self.visible = value
        self._enabled = value



    @property
    def focus(self):
        # receive shortcuts when no other widget is in focus
        return WidgetEventReactor.focus is self or WidgetEventReactor.focus is None

    # use same setter as in the superclass:
    focus = focus.setter(Widget.focus.fset)


###############
#
# Layout Widgets
#
##############

class CrossV2(V2):
    #__slots__ = ("axis", "cross")
    def __new__(cls, x=0, y=0, axis="x", length=None, width=None):
        if axis == "x":
            x = x if length is None else length
            y = y if width is None else width
        else:
            x = x if width is None else width
            y = y if length is None else length

        return super().__new__(cls, x, y)

    def __init__(self, x=0, y=0, axis="x", length=None, width=None):
        self.axis = axis
        self.cross = "y" if axis == "x" else "x"

    length = property(lambda s: getattr(s, s.axis))
    width = property(lambda s: getattr(s, s.cross))
    V2 = property(lambda s: V2(s.x, s.y))


class Container(Widget):
    pass


class _Box(Container):
    # abstract - use either HBox or VBox

    axis = None

    def __init__(self, *args, padding=0, **kw):
        self.children = []
        self.padding = padding
        self.border = kw.pop("border", None)
        super().__init__(*args, size=(1, 1), focus_position=None, **kw)

    def add(self, widget):
        events.Subscription(events.WidgetResize, self._child_resized, guard=lambda event: event.widget is widget)
        anchor = getattr(widget, "anchor", "end")
        if anchor == "start":
            self.children.insert(0, widget)
        else:
            self.children.append(widget)

    register_child = add

    def _child_resized(self, event):
        widget = event.widget
        self.reorganize()

    def reorganize(self):
        axis = self.axis
        padding = CrossV2(length = self.padding, axis=axis)
        new_size = CrossV2(0, 0, axis=axis)
        for widget in self.children:
            widget_size = CrossV2(widget.size, axis=axis)
            current_pos = new_size.length + padding.length
            widget.sprite.pos = CrossV2(length=current_pos, axis=axis).V2
            new_size = CrossV2(length=current_pos + widget_size.length, width=max(new_size.width, widget_size.width), axis=axis)
        self.size = new_size.V2

    focus = property(lambda s: False, lambda s, v: None)

class VBox(_Box):
    axis = "y"

class HBox(_Box):
    axis = "x"
