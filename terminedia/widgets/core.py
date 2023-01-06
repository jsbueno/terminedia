from collections.abc import Iterable
from math import ceil

import terminedia

from terminedia.sprites import Sprite
from terminedia import events, V2

from terminedia.events import EventSuppressFurtherProcessing
from terminedia.input import KeyCodes
from terminedia.text import plane_names
from terminedia.text.planes import forward_char_size


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

class WidgetCancelled(Exception):
    pass


class FocusTransformer(terminedia.Transformer):

    bg_color = terminedia.Color((.3, .3, .3))

    def background(self, source, background, pos):
        if not (pos[0] in (0, source.size[0] - 1) or pos[1] in (0, source.size[1] - 1)):
            return background
        return self.bg_color
        #if background is terminedia.DEFAULT_BG:
            #background = self.bg_color


def _ensure_extend(seq, value):
    if isinstance(value, Iterable):
        seq.extend(value)
    elif value is not None:
        seq.append(value)


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
                # FIXME: not quite right. maybe check all hit sprites first, then execute callbacks in reverse "z-order"
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

        if isinstance(parent, Sprite):
            parent = parent.shape

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

    @active.setter
    def active(self, value):
        self.sprite.active = False

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
        size = (text_size * forward_char_size[text_plane]).ceil
        shape = terminedia.shape(size + padding)
        sprite = Sprite(shape)
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



class Container(Widget):
    pass

class ModalMisc:
    def __init__(self, *args, **kw):
        super.__init__(*args, **kw)
        self.sprite.raise_()
