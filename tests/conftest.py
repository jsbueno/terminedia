import io
from unittest import mock

import terminedia as TM

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--DISPLAY",
        action="store_true",
        help="Output terminedia drawings on terminal for some tests. Requires '-s' option ",
    )
    parser.addoption(
        "--DELAY",
        action="store",
        type=float,
        default=0.2,
        help="Time to wait after tests with visual output",
    )


fast_and_slow_render_mark = (
    "set_render_method",
    [
        (lambda: setattr(TM.context, "fast_render", False)),
        (lambda: setattr(TM.context, "fast_render", True)),
    ],
)


def rendering_test(func):
    # @wraps(func)
    def rendering_test(set_render_method, DISPLAY, DELAY):
        set_render_method()
        stdout = io.StringIO()

        fn = func()
        with mock.patch("sys.stdout", stdout):
            next(fn)

        if DISPLAY:
            print(stdout.getvalue())
            TM.pause(DELAY)
        try:
            fn.send(stdout.getvalue())
        except StopIteration:
            pass

    # functools.wraps won't do in this case: py.test must "see" the original name _and_ the
    # wrapper's signature, not the signarure from the decorated function
    rendering_test.__name__ = func.__name__

    return rendering_test


@pytest.fixture()
def DISPLAY(pytestconfig):
    return pytestconfig.getoption("DISPLAY")


@pytest.fixture()
def DELAY(pytestconfig):
    return pytestconfig.getoption("DELAY")
