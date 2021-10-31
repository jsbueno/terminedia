from collections import namedtuple
from collections.abc import Mapping
from inspect import isawaitable
from math import ceil

import terminedia

from terminedia import Transformer, Directions

from terminedia import events, V2

from terminedia.events import EventSuppressFurtherProcessing
from terminedia.input import KeyCodes
from terminedia.text.style import MLTokenizer


from .core import WidgetEventReactor, Widget, _ensure_extend, Container


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

        self.min_height = min_height
        self.max_height = max_height or parent.size.y
        self.min_width = min_width
        self.max_width = max_width

        self.load_options(options, redraw=False)

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
        self.selected_row = selected_row
        self.transformer = SelectorTransformer(self)
        self.callback = callback

        self.sprite.transformers.append(self.transformer)

    def load_options(self, options, redraw=True):
        if isinstance(options, dict):
            str_options = list(options.keys())
            options_values = list(options.values())
        else:
            str_options = [opt[0] if isinstance(opt, tuple) else opt for opt in options]
            options_values = [(opt[1] if isinstance(opt, tuple) else opt) for str_opt, opt in zip(str_options, options) ]

        self.options = [_selector_option(opt, val, self._stripped_opt(opt)) for opt, val in zip(str_options, options_values)]
        self.str_options = str_options
        if redraw:
            self.offset = 0
            self.selected_row = 0
            self.redraw()

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
        pass

    def _poschange(self):
        pass

    def __setitem__(self, index, value):
        if isinstance(value, str):
            value = _selector_option(value, value, self._stripped_opt(value))
        elif len(value) == 2:
            value = _selector_option(value[0], value[1], self._stripped_opt(value[0]))

        prev_size = self.size
        self.options[index] = value
        self.str_options[index] = str(value)
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

    Each key in the dictionary should map to a two-tuple, where the first
    element is an optional callable action - if given as None, the command is
    ignored and non clickable: other parts of the app should handle that shortcut.
    The second element of the tuple is the description for the action

    If the key maps to a dictionary, that is used as another menu-level.

    The menu visibility is optionally toggable  if an action in the current level is the string "toggle":
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


class _Box(Container):
    # abstract - use either HBox or VBox

    axis = None
    _fixed_size = False

    def __init__(self, *args, padding=0, **kw):
        self.children = []
        self.padding = padding
        self.border = kw.pop("border", None)
        super().__init__(*args, size=kw.pop("size", (1, 1)), focus_position=None, **kw)

    def add(self, widget):
        events.Subscription(events.WidgetResize, self._child_resized, guard=lambda event: event.widget is widget)
        anchor = getattr(widget, "anchor", "end")
        if anchor == "start":
            self.children.insert(0, widget)
        else:
            self.children.append(widget)

    register_child = add

    def _child_resized(self, event):
        # widget = event.widget
        self.reorganize()

    def reorganize(self):
        if self._fixed_size:
            return
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
