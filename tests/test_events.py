import pytest

from terminedia.events import dispatch, Event, Subscription, EventTypes

def test_event_system_subscripton_queue_works():
    subscription = Subscription(EventTypes.Tick)

    assert subscription.queue is not None and not subscription.queue

    e = Event(EventTypes.Tick)
    dispatch(e)
    assert subscription.queue and subscription.queue.popleft() is e
