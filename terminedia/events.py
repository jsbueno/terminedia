import asyncio
import time

from collections import deque
from collections.abc import Iterator
from copy import copy
from itertools import chain
from weakref import WeakSet
import inspect
import os
import signal


from terminedia.utils import IterableFlag, V2
import terminedia


#: Inner, process-wide event queue.
#: Events dispatched are place on it, untill something calls
#: events.process, which will be sent to subscribers or discarded.
#: (Screen.update has an implicit call to events.process)
_event_queue = deque()

_sigwinch_counter = 0
_original_sigwinch = None


class EventMessage(Exception):
    pass

class EventSuppressFurtherProcessing(EventMessage):
    pass


class EventTypes(IterableFlag):
    Tick = 1
    KeyPress = 2
    Phrase = 4  # Emitted on enter press
    MouseMove = 8
    MousePress = 16
    MouseRelease = 32
    MouseClick = 64
    MouseDoubleClick = 128
    TerminalSizeChange = 256
    WidgetResize = 512
    Custom = 1024
    QuitLoop = 2048



# Get rid of the "EventTypes" namespaces:
# make names above avaliable from TM.events.NAME
for event in EventTypes:
    globals()[event.name] = event


def event_nuke(guard):
    to_kill = []
    for index, event in enumerate(_event_queue):
        if guard(event):
            to_kill.append(index)
    for index in reversed(to_kill):
        _event_queue.pop(index)


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
        self.tick = kwargs.pop("tick", None) or get_current_tick()
        self.type = type

        if dispatch:
            _event_dispatch(self)

    def copy(self, **kwargs):
        ev = copy(self)
        ev.__dict__.update(kwargs)
        return ev

    def __repr__(self):
        return f"Event <{self.type}> {self.__dict__}"


class Subscription:
    subscriptions = {}

    def __init__(self, event_types, callback=None, guard=None):
        cls = self.__class__
        self.callback = self.queue = None
        self.guard = guard
        if callback:
            self.callback = callback
        else:
            self.queue = deque()
        self.types = event_types
        for type_ in event_types:
            cls.subscriptions.setdefault(type_, []).append(self)
        self.resolution = .005
        self.terminated = False

    def __bool__(self):
        if self.callback:
            return True
        return bool(self.queue)

    def __aiter__(self):
        return self

    async def __anext__(self):
        # callbackless subscriptions can be used in an async-for to fetch events
        if self.callback:
            raise TypeError("Subscriptions with a callback set can't be iterated")
        while not self.terminated:
            if self.queue:
                return self.queue.popleft()
            await asyncio.sleep(self.resolution)
            # HACK: pump keyboard events if not in a Screen context
            if KeyPress in self.types:
                terminedia.inkey(consume=False)
            process()

        raise StopAsyncIteration()

    def kill(self):
        for type in self.types:
            self.__class__.subscriptions[type].remove(self)
        self.terminated = True

    def prioritize(self):
        """move this subscription so that it receives the event first

        So that widgets that have focus can process keyboard touch or mouse events
        and supress the event for other subscribers.

        """
        cls = self.__class__
        for type_ in self.types:
            try:
                cls.subscriptions[type_].remove(self)
            except ValueError:
                pass
            cls.subscriptions[type_].append(self)

    def __repr__(self):
        return f"Subscription {self.types}{', callback: ' + repr(self.callback) if self.callback else '' }"

class _SystemSubscription(Subscription):
    """Used internally for low level event handling
    (for example: convert two-close clicks into a double-click)

    Works just like subscriptions, but have a separate registry.
    Also, these are always processed first than "User" subscriptions, so that
    an EventSuppressFurtherProcessing exception will not prevent the lower level handling
    """
    subscriptions = {}


def dispatch(event):
    """Queues any event to be dispatchd latter, when "process" is called.

    An Event will normally call this implicitly when instantiated. But
    if one pass it `dispatch=False` upon instantiation,
    (for example, to set extra attributes before sending it away)
    this have to be called manually.
    """
    _event_queue.append(event)


# Alias so this function can be called by another name inside Event.__init__
_event_dispatch = dispatch


def list_subscriptions(type_: EventTypes, _system=False) -> Iterator:
    """Returns a set with all active subscriptions for the given event type"""
    if _system:
        system_events = reversed(_SystemSubscription.subscriptions.get(type_, []))
    else:
        system_events = []
    return chain(system_events, reversed(Subscription.subscriptions.get(type_, [])))


def _event_process_handle_coro(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        raise RuntimeError("An event subscription is being run in a co-routine, but the event" \
            "system is not running in an asyncio loop. Use terminedia.terminedia_main to run an asyncio event loop")

    task = loop.create_task(coro)
    # FIXME: add a proper callback which can handle eventual exceptions
    # task.add_done_callback(task.result)
    # TODO: add the task to a collection, and at some point collect the results of done tasks.


def process():
    """Sends any created events since the last call to their subscribers.

    Screen.update, and interations on subscriptions will call this regularly;

    """

    # Event processing in callbacks is synchronous, and as the callbacks
    # can create other events, we have to copy the queue on each interaction
    # to prevent the queue from being changed during interaction.

    events = deque(_event_queue)
    _event_queue.clear()
    while  events:
        for event in events:
            for subscription in list_subscriptions(event.type, _system=True):
                if subscription.guard and not subscription.guard(event):
                    continue
                if subscription.callback:
                    try:
                        result = subscription.callback(event)
                        if inspect.isawaitable(result):
                            _event_process_handle_coro(result)
                    except EventSuppressFurtherProcessing:
                        break
                else:
                    subscription.queue.append(event)
        events = deque(_event_queue)
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



# These work as decorators for the events.
# (The usual way to dispatch events is calling "Screen.update")
keypress_handler = lambda func: Subscription(EventTypes.KeyPress, func).callback
mouseclick_handler = lambda func: Subscription(EventTypes.MouseClick, func).callback
mouse_handler = lambda func: Subscription(EventTypes.MouseClick | EventTypes.MouseMove | EventTypes.MousePress | EventTypes.MouseRelease, func).callback


