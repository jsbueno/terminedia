import time

from collections import deque
from weakref import WeakSet
import os
import signal


from terminedia.utils import IterableFlag, V2


#: Inner, process-wide event queue.
#: Events dispatched are place on it, untill something calls
#: events.process, which will be sent to subscribers or discarded.
#: (Screen.update has an implicit call to events.process)
_event_queue = deque()

_sigwinch_counter = 0
_original_sigwinch = None



class EventTypes(IterableFlag):
    Tick = 1
    KeyPress = 2
    Phrase = 4  # Emitted on enter press
    MouseMove = 8
    MousePress = 16
    MouseRelease = 32
    MouseClick = 64
    TerminalSizeChange = 128
    Custom = 256


class Event:
    def __init__(self, type, dispatch=True, **kwargs):
        """Event object - used to deliver messages across various
        program units in animations or interactive apps.

        Args:
          - type (EventTypes): The event type
          - dispatch (bool): whether the event should automatically queue itself
                for being consumed. Default: True
          - kwargs: any other attributes that should be set on the Event object.
        """
        from terminedia.utils import get_current_tick
        self.__dict__.update(kwargs)
        self.timestamp = time.time()
        self.tick = get_current_tick()
        self.type = type

        if dispatch:
            _event_dispatch(self)

    def __repr__(self):
        return f"Event <{self.type}> {self.__dict__}"


class Subscription:
    subscriptions = {}

    def __init__(self, event_types, callback=None):
        cls = self.__class__
        self.callback = self.queue = None
        if callback:
            self.callback = callback
        else:
            self.queue = deque()
        self.types = event_types
        for type_ in event_types:
            cls.subscriptions.setdefault(type_, set()).add(self)

    def kill(self):
        for type in self.types:
            self.__class__.subscriptions[type].remove(self)

    def __repr__(self):
        return f"Subscription {self.types}{', callback: ' + repr(self.callback) if self.callback else '' }"


def dispatch(event):
    """Queues any event to be dispatchd latter, when "process" is called.

    An Event will normally call this implicitly when instantiated. But
    if one pass it `dispatch=False` upon instanciation, this have to be
    called manually.
    """
    _event_queue.append(event)

# Alias so the function can be called by another name in Event.__init__
_event_dispatch = dispatch


def process():
    """Sends any created events since the last call to their subscribers.

    Screen.update will call this regularly - programs
    not using Screen.update should call this on each iteration
    """
    for event in _event_queue:
        for subscription in Subscription.subscriptions.get(event.type, ()):
            if subscription.callback:
                subscription.callback(event)
            else:
                subscription.queue.append(event)
    _event_queue.clear()



def window_change_handler(signal_number, frame):
    """Called as a signal to terminal-window resize

    It is set as a handler on terminedia.Screen instantiation,
    and will automatically add window-resize events on
    terminedia event system.
    """

    new_size = V2(os.get_terminal_size())
    Event(EventTypes.TerminalSizeChange, size=new_size, dispatch=True)


def _register_sigwinch():
    # Called automatically on "Screen" instantiation.
    # An app not using Screen that care about handling window reszing could call this manually.

    global _sigwinch_counter, _original_sigwinch
    if not getattr(signal, "SIGWINCH", ""):
        # Non Posix platform have no sigwinch - terminal size change have
        # to be detected by other means.
        return
    if _sigwinch_counter == 0:
        _original_sigwinch = signal.getsignal(signal.SIGWINCH)

    _sigwinch_counter += 1

    signal.signal(signal.SIGWINCH, window_change_handler)


def _unregister_sigwinch():
    # meant to be called by Screen.__del__ - which will very little likely take
    # place more than once per app. And no matter if it it fails to be called
    # on app shutdown
    global _sigwinch_counter
    if not getattr(signal, "SIGWINCH", "") or not _sigwinch_counter:
        return
    _sigwinch_counter -= 1
    if _sigwinch_counter == 0 and _original_sigwinch:
        signal.signal(signal.SIGWINCH, _original_sigwinch)



