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


@pytest.fixture()
def DISPLAY(pytestconfig):
    return pytestconfig.getoption("DISPLAY")


@pytest.fixture()
def DELAY(pytestconfig):
    return pytestconfig.getoption("DELAY")
