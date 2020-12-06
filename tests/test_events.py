import pytest

from terminedia.events import dispatch, Event, Subscription, EventTypes, process


def test_event_system_subscripton_queue_works():
    subscription = Subscription(EventTypes.Tick)

    assert subscription.queue is not None and not subscription.queue

    e = Event(EventTypes.Tick)
    process()
    assert subscription.queue and subscription.queue.popleft() is e


def test_event_system_subscripton_callback_works():
    callback_called = False
    def callback(event):
        nonlocal callback_called
        callback_called = True

    subscription = Subscription(EventTypes.Tick, callback=callback)

    assert subscription.queue is None and subscription.callback

    e = Event(EventTypes.Tick)
    process()
    assert callback_called
    assert subscription.queue is None


def test_event_system_select_events():
    subscription = Subscription([0, 1])
    Event(2)
    process()
    assert not subscription.queue
    Event(0)
    process()
    assert subscription.queue
    subscription.queue.clear()
    Event(1)
    process()
    assert subscription.queue
