import time

from collections import deque
from weakref import WeakSet

from terminedia.utils import IterableFlag


#: Inner, process-wide event queue.
#: Events dispatched are place on it, untill something calls
#: events.process, which will be sent to subscribers or discarded.
#: (Screen.update has an implicit call to events.process)
_event_queue = deque()



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
        for type in self.event_types:
            self.__class__.subscriptions[type].remove(self)

    def __repr__(self):
        return f"Subscription {self.types}{', callback: ' + repr(self.callback) if self.callback else '' }"


def dispatch(event):
    """Queues any event to be dispatchd latter, when "process" is called"""
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

