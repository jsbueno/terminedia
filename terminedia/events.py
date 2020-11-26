import time

from collections import deque
from weakref import WeakSet

from terminedia.utils import IterableFlag


class EventTypes(IterableFlag):
    Tick = 1
    KeyPress = 2
    Phrase = 4  # Emitted on enter press
    MouseMove = 8
    MousePress = 16
    MouseRelease = 32
    MouseClick = 64
    Custom = 128


class Event:
    def __init__(self, type, **kwargs):
        from terminedia.utils import get_current_tick
        self.__dict__.update(kwargs)
        self.timestamp = time.time()
        self.tick = get_current_tick()
        self.type = type

    def __repr__(self):
        return f"Event <{self.type}>"


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
    for subscription in Subscription.subscriptions.get(event.type, ()):
        if subscription.callback:
            subscription.callback(event)
        else:
            subscription.queue.append(event)
