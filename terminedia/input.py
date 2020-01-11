"""non-blocking Keyboard reading and other input related code
"""
import os
import sys
import time

from collections import defaultdict, namedtuple
from contextlib import contextmanager

from terminedia.utils import mirror_dict


# Keyboard reading code copied and evolved from
# https://stackoverflow.com/a/6599441/108205
# (@mheyman, Mar, 2011)


@contextmanager
def _posix_keyboard():
    """
    This context manager reconfigures `stdin` so that key presses
    are read in a non-blocking way.

    Inside a managed block, the :any:`inkey` function can be called and will
    return whether a key is currently pressed, and which it is.

    An app that will make use of keyboard reading alongside screen
    controling can enter both this and an instance of :any:`Screen` in the
    same "with" block.

    (Currently Posix only)

    """
    fd = sys.stdin.fileno()
    # save old state
    flags_save = fcntl.fcntl(fd, fcntl.F_GETFL)
    attrs_save = termios.tcgetattr(fd)
    # make raw - the way to do this comes from the termios(3) man page.
    attrs = list(attrs_save)  # copy the stored version to update
    # iflag
    attrs[0] &= ~(
        termios.IGNBRK
        | termios.BRKINT
        | termios.PARMRK
        | termios.ISTRIP
        | termios.INLCR
        | termios.IGNCR
        | termios.ICRNL
        | termios.IXON
    )
    # oflag
    attrs[1] &= ~termios.OPOST
    # cflag
    attrs[2] &= ~(termios.CSIZE | termios.PARENB)
    attrs[2] |= termios.CS8
    # lflag
    attrs[3] &= ~(
        termios.ECHONL | termios.ECHO | termios.ICANON | termios.ISIG | termios.IEXTEN
    )
    termios.tcsetattr(fd, termios.TCSANOW, attrs)
    fcntl.fcntl(fd, fcntl.F_SETFL, flags_save | os.O_NONBLOCK)
    try:
        yield
    finally:
        # restore old state
        termios.tcsetattr(fd, termios.TCSAFLUSH, attrs_save)
        fcntl.fcntl(fd, fcntl.F_SETFL, flags_save)


def _posix_inkey(break_=True, clear=True):
    """Return currently pressed key as a string

    Args:
      - break\_ (bool): Boolean parameter specifying whether "CTRL + C"
        (\x03) should raise KeyboardInterrupt or be returned as a
        keycode. Defaults to True.
      -clear (bool): clears the keyboard buffer contents

    *Important*: This function only works inside a
    :any:`keyboard` managed context. (Posix)

    Code values or code sequences for non-character keys,
    like ESC, direction arrows, fkeys are kept as constants
    in the "KeyCodes" class.

    Unfortunatelly, due to the nature of console streaming,
    this can't receive "keypress" or "keyup" events, and repeat-rate
    is not configurable, nor can it detect modifier keys, or
    simultaneous key-presses.

    """
    keycode = ""

    if clear:
        c = sys.stdin.read(10000)
        if c:
            c = c[
                c.rfind("\x1b") :
            ]  # if \x1b is not found, rfind returns -1, which is the desired value
    else:
        c = sys.stdin.read(1)  # returns a single character

    while True:
        if not c:
            break
        if c == "\x03" and break_:
            raise KeyboardInterrupt
        keycode += c
        if (len(keycode) == 1 or keycode in KeyCodes.codes) and keycode != "\x1b":
            break
        c = sys.stdin.read(1)

    return keycode


def getch(timeout=0) -> str:
    """Enters non-blocking keyboard mode and returns the first keypressed
    Args:
      - timeout (float): time in seconds to wait. If 0 (default), waits forever

    """
    step = 1 / 30
    ellapsed = step
    with keyboard():
        time.sleep(step)
        key = inkey()
        while not key:
            key = inkey()
            time.sleep(step)
            ellapsed += step
            if timeout and ellapsed >= timeout:
                key = ""
                break
    return key


def pause(timeout=0) -> None:
    """Enters non-blocking keyboard mode and waits for any keypress
    Args:
      - timeout (float): time in seconds to wait. If 0 (default), waits forever

    """
    getch(timeout)

def _testkeys():
    """Debug function to print out keycodes as read by :any:`inkey`"""
    with keyboard():
        while True:
            try:
                key = inkey()
            except KeyboardInterrupt:
                break
            if key:
                print("", key.encode("utf-8"), end="", flush=True)
            print(".", end="", flush=True)
            time.sleep(0.3)


class _posix_KeyCodes:
    """Character keycodes as they appear in stdin

    (and as they are reported by :any:`inkey` function). This class
    is used only as a namespace. Also note that printable-character
    keys, such as upper and lower case letters, numbers and symbols
    are not listed here, as their "code" is just a string containing
    themselves.
    """

    F1 = "\x1bOP"
    F2 = "\x1bOQ"
    F3 = "\x1bOR"
    F4 = "\x1bOS"
    F5 = "\x1b[15~"
    F6 = "\x1b[17~"
    F7 = "\x1b[18~"
    F8 = "\x1b[19~"
    F9 = "\x1b[20~"
    F10 = "\x1b[21~"
    F11 = "\x1b[23~"
    F12 = "\x1b[24~"
    ESC = "\x1b"
    BACK = "\x7f"
    DELETE = "\x1b[3~"
    ENTER = "\r"
    PGUP = "\x1b[5~"
    PGDOWN = "\x1b[6~"
    HOME = "\x1b[H"
    END = "\x1b[F"
    INSERT = "\x1b[2~"
    UP = "\x1b[A"
    RIGHT = "\x1b[C"
    DOWN = "\x1b[B"
    LEFT = "\x1b[D"

    codes = mirror_dict(locals())


@contextmanager
def _win32_keyboard():
    """
    This context manager is available to offer compatibility with the Posix equivalent. 

    It is not really needed under Windows.

    """
    try:
        yield
    finally:
        pass



def _win32_inkey(break_=True, clear=True):
    """Return currently pressed key as a string

    Args:
      - break\_ (bool): Boolean parameter specifying whether "CTRL + C"
        (\x03) should raise KeyboardInterrupt or be returned as a
        keycode. Defaults to True.
      -clear (bool): clears the keyboard buffer contents

    *Important*: This function only works inside a
    :any:`keyboard` managed context. (Posix)

    Code values or code sequences for non-character keys,
    like ESC, direction arrows, fkeys are kept as constants
    in the "KeyCodes" class.

    Unfortunatelly, due to the nature of console streaming,
    this can't receive "keypress" or "keyup" events, and repeat-rate
    is not configurable, nor can it detect modifier keys, or
    simultaneous key-presses.

    """

    if not msvcrt.kbhit():
        return ""
    
    code = msvcrt.getwch()
    if code in "\x00à" : # and msvcrt.kbhit():
        code += msvcrt.getwch()

    return code


def _testkeys():
    """Debug function to print out keycodes as read by :any:`inkey`"""
    with keyboard():
        while True:
            try:
                key = inkey()
            except KeyboardInterrupt:
                break
            if key:
                print("", key.encode("utf-8"), end="", flush=True)
            print(".", end="", flush=True)
            time.sleep(0.3)


class _win32_KeyCodes:
    """Character keycodes as they appear in stdin

    (and as they are reported by :any:`inkey` function). This class
    is used only as a namespace. Also note that printable-character
    keys, such as upper and lower case letters, numbers and symbols
    are not listed here, as their "code" is just a string containing
    themselves.
    """

    F1 = "\x00;"
    F2 = "\x00<"
    F3 = "\x00="
    F4 = "\x00>"
    F5 = "\x00?"
    F6 = "\x00@"
    F7 = "\x00A"
    F8 = "\x00B"
    F9 = "\x00C"
    F10 = "\x00D"
    F11 = "á\x85"
    F12 = "á\x86"
    ESC = "\x1b"
    BACK = "\x08"
    DELETE = "à5"
    ENTER = "\r"
    PGUP = "àI"
    PGDOWN = "àQ"
    HOME = "àG"
    END = "àO"
    INSERT = "àR"
    UP = "àH"
    RIGHT = "àM"
    DOWN = "àP"
    LEFT = "àK"

    codes = mirror_dict(locals())


if sys.platform != "win32":
    import fcntl
    import termios

    inkey = _posix_inkey
    keyboard = _posix_keyboard
    KeyCodes = _posix_KeyCodes
else:
    import msvcrt
    inkey = _win32_inkey
    keyboard = _win32_keyboard
    KeyCodes = _win32_KeyCodes


