import io
from unittest import mock

import terminedia as TM
from terminedia.utils import combine_signatures

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


fast_render_mark = (
    "set_render_method",
    [
        (lambda: setattr(TM.context, "fast_render", True)),
    ],
)


def rendering_test(func):
    @combine_signatures(func)
    def rendering_test(*args, set_render_method, DISPLAY, DELAY, **kwargs):
        set_render_method()
        stdout = io.StringIO()

        fn = func(*args, **kwargs)
        with mock.patch("sys.stdout", stdout):
            next(fn)

            while True:

                if DISPLAY:
                    print(stdout.getvalue())
                    TM.pause(DELAY)
                try:
                    fn.send(stdout.getvalue())
                    stdout.seek(0)
                    stdout.truncate()
                except StopIteration:
                    break

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
