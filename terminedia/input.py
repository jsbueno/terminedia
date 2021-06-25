"""non-blocking Keyboard reading and other input related code
"""
import enum
import io
import os
import re
import sys
import time

import typing as T

from collections import defaultdict, deque, namedtuple
from contextlib import contextmanager

from terminedia.utils import mirror_dict, V2, contextkwords
from terminedia.events import Event, EventTypes, list_subscriptions


class KeyboardBase:
    # abstract
    def __init__(self):
        self.enabled = 0

    def __enter__(self):
        pass

    def __exit__(self, *args):
        pass

    def inkey(self, break_=True, clear=True):
        pass

    def __call__(self):
        return self


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
    TAB = "\t"
    SHIFT_TAB = "\x1b[Z"

    codes = mirror_dict(locals())


class _PosixKeyboard(KeyboardBase):

    # Keyboard reading code copied and evolved from
    # https://stackoverflow.com/a/6599441/108205
    # (@mheyman, Mar, 2011)

    def __init__(self):
        super().__init__()
        self._last_pressed_after_ESC = False
        self.not_consumed = deque()

    def __enter__(self):
        """
        This context manager reconfigures `stdin` so that key presses
        are read in a non-blocking way.

        Inside a managed block, the :any:`inkey` function can be called and will
        return whether a key is currently pressed, and which it is.

        An app that will make use of keyboard reading alongside screen
        controling can enter both this and an instance of :any:`Screen` in the
        same "with" block.

        """
        self.fd = sys.stdin.fileno()
        # save old state
        if self.enabled == 0:
            self.flags_save = fcntl.fcntl(self.fd, fcntl.F_GETFL)
            self.attrs_save = termios.tcgetattr(self.fd)
        # make raw - the way to do this comes from the termios(3) man page.
        attrs = list(self.attrs_save)  # copy the stored version to update

        # Check flags at https://linux.die.net/man/3/termios
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
        termios.tcsetattr(self.fd, termios.TCSANOW, attrs)
        fcntl.fcntl(self.fd, fcntl.F_SETFL, self.flags_save | os.O_NONBLOCK)
        self.enabled += 1
        return self

    def __exit__(self, exc_type, exc_value, tb):
        # restore old state
        self.enabled -= 1
        if self.enabled <= 0:
            self.reset()


    def reset(self):
        if hasattr(self, "attrs_save"):
            termios.tcsetattr(self.fd, termios.TCSAFLUSH, self.attrs_save)
            fcntl.fcntl(self.fd, fcntl.F_SETFL, self.flags_save)
        self.enabled = 0
        self._last_pressed_after_ESC = ""

    def _scan_code(self, stream):

        composed = ""
        while True:
            # read byte by byte, so that no extra input is consumed from stdin
            if self._last_pressed_after_ESC:
                next_char = self._last_pressed_after_ESC
            else:
                next_char = stream.read(1)
            if not next_char:
                return composed, True
            # There is one special case, when "ESC" is pressed in non-clearing mode:
            # we should not have read the next token, but it is already fetched by now.
            if len(composed) == 2 and composed[0] == "\x1b" and composed[1] != "[":
                self._last_pressed_after_ESC = composed[1]
                return composed[0], False

            self._last_pressed_after_ESC = ""
            composed += next_char
            if composed == "\x1b":
                continue
            if len(composed) == 1 or composed in self.keycodes.codes or len(composed) > 30:
                return composed, False

            # "mouse" is a module alias for the singleton of the posix-mouse reader, defined bellow.
            if mouse.enabled:
                # mouse.match consumes the token
                m = mouse.match(composed)
                if m:
                    return "", False


    def inkey(self, break_=True, clear=True, consume=True):
        """Return currently pressed key as a string

        This is the implemenation of old 8-bit basic "inkey" and "inkey$" builtins,
        and also the heart of the keybard input system.

        Args:
        - break\_ (bool): Boolean parameter specifying whether "CTRL + C"
            (\x03) should raise KeyboardInterrupt or be returned as a
            keycode. Defaults to True.
        - clear (bool): clears the keyboard buffer contents.
                If False, queued keyboard codes are returned in order, for each call
                Otherwise queued codes are discarded and only the last-pressed character
                if returned. Even when "clear" is True, one keyboard event
                is generated for each token.
                Also, note that calling Screen.update will cause this to be called
                with clear=True, to flush all keypress events. Applications using
                'inkey' to read all input should make all the calls between 'updates'
                defaults to True
        - consume: remove the received key from keypresses. When using an event-based
                approach, this function is responsible for dispatching the events, and
                have to be called. The default behavior, however, will make keypresses
                go missing when "inkey" is called to read the keyboard with the even system on.
                TL;DR: the calls to inkey made by the inner event system should pass
                False to this parameter, otherwise leave it as is.

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
        # In this context, 'token' is either a single-char string, representing an
        # 'ordinary' keypress or an escape sequence representing a special key or mouse event.

        if not self.enabled:
            raise RuntimeError("keyboard context manager must be entered to enable non-blocking keyboard reads")

        if self.not_consumed and consume:
            return self.not_consumed.popleft()

        last_emitted = old_keycode = ""

        if not clear:
            buffer = sys.stdin
        else:
            # read all buffer, generate events for all tokens
            # but return only the last event
            # (so, the caller to "inkey" have info on the last pressed key)
            buffer = io.StringIO(sys.stdin.read(10000))
            buffer.seek(0)

        while True:
            keycode, stream_eof = self._scan_code(buffer)
            if stream_eof and not keycode:
                keycode = old_keycode
            if keycode == '\x03' and break_:
                raise KeyboardInterrupt()
            if keycode and list_subscriptions(EventTypes.KeyPress):
                if not(last_emitted == keycode and old_keycode == keycode):
                    Event(EventTypes.KeyPress, key=keycode)
                last_emitted = keycode
            if not clear or stream_eof:
                # next characters will be consumed in next calls
                break
            old_keycode = keycode
        if not consume:
            self.not_consumed.append(keycode)
        if mouse.enabled and mouse.on_hold_clicks:
            mouse.flush_clicks()
        return keycode

    keycodes = _posix_KeyCodes


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
    TAB = "\t"
    SHIFT_TAB = "\x1b[Z"  # FIXME: not this - have to be checked on a win box.

    codes = mirror_dict(locals())


class _WindowsKeyboard(KeyboardBase):
    def __enter__(self):
        """
        This context manager is available to offer compatibility with the Posix equivalent.

        It is not really needed under Windows, as the keyboard input is got via
        a "side channel" API.

        """
        self.enabled += 1
        return self

    def __exit__(self, exc_type, exc_value, tb):
        self.enabled -= 1



    def inkey(self, break_=True, clear=True, consume=True):
        """Return currently pressed key as a string

        Args:
        - break\_ (bool): Boolean parameter specifying whether "CTRL + C"
            (\x03) should raise KeyboardInterrupt or be returned as a
            keycode. Defaults to True.
        - clear (bool): clears the keyboard buffer contents


        [WIP: latest updates adding support for the event system
        on the posix side where not reflected here]
        [TODO: Dispatch mouse event handling from here]

        """

        if not msvcrt.kbhit():
            return ""

        code = msvcrt.getwch()
        if code in "\x00à" : # and msvcrt.kbhit():
            code += msvcrt.getwch()

        if list_subscriptions(EventTypes.KeyPress):
            Event(EventTypes.KeyPress, key=keycode)

        return code

    keycodes = _win32_KeyCodes


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


@contextkwords
def input(prompt="", maxwidth=None, insert=True):
    import asyncio
    from terminedia.asynchronous import ainput

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        # when there is no loop and not on main thread:
        # for example, from within ipython
        loop = asyncio.new_event_loop()


    input_coro = ainput(prompt, maxwidth, insert)

    if loop.is_running():
        raise RuntimeError("In async contexts, use terminedia.ainput instead")
    return loop.run_until_complete(input_coro)


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


def _testmouse():
    # https://stackoverflow.com/questions/59864485/capturing-mouse-in-virtual-terminal-with-ansi-escape
    # change stdin and stdout into unbuffered
    with keyboard():
        # ignite mouse through ancient, unknown brujeria
        sys.stdout.write("\x1b[?1003h\x1b[?1015h\x1b[?1006h")
        #sys.stdout.write("\x1b[?1005h") #\x1b[?1015h\x1b[?1006h")
        sys.stdout.flush()
        counter = 0
        while counter < 200:

            data = sys.stdin.buffer.read(16)
            if data:
                print(data)
            time.sleep(0.05)
            counter += 1

    print("\x1b[?1005l")



class MouseButtons(enum.IntFlag):
    Button1 = 1
    Button2 = 2
    Button3 = 4
    MouseWheelUp = 8
    MouseWheelDown = 16
    Button4 = 8     # SIC: this is an alias
    Button5 = 16
    Button6 = 32
    Button7 = 64


_button_map = {
    0: MouseButtons.Button1,
    1: MouseButtons.Button2,
    2: MouseButtons.Button3,
    64: MouseButtons.Button4,
    65: MouseButtons.Button5,
    128: MouseButtons.Button6,
    129: MouseButtons.Button7,
}


class _Mouse:

    CLICK_THRESHOLD = 0.3
    DOUBLE_CLICK_THRESHOLD = 0.3

    def __init__(self):
        # TBD: check for re-entering?
        self.enabled = False
        self.last_click = self.last_press = (0, 0)
        self.on_hold_clicks = []

    def __enter__(self):
        self.keyboard = keyboard()
        self.keyboard.__enter__()
        self.enabled = True
        # sys.stdout.write("\x1b[?1005h")
        sys.stdout.write("\x1b[?1003h\x1b[?1015h\x1b[?1006h")
        sys.stdout.flush()

    def __exit__(self, *args):
        sys.stdout.write("\x1b[?1003l")
        sys.stdout.flush()
        self.enabled = False
        self.keyboard.__exit__(*args)


    def match(self, sequence):
        # The ANSI sequence for a mouse event in mode 1006 is '<ESC>[B;Col;RowM' (last char is 'm' if button-release)
        m = re.match(r"\x1b\[\<(?P<button>\d+);(?P<column>\d+);(?P<row>\d+)(?P<press>[Mm])", sequence)
        if not m:
            return None
        params = m.groupdict()
        pressed = params["press"] == "M"
        button = _button_map.get(int(params["button"]) & (~0x20), None)
        moving = bool(int(params["button"]) & 0x20)

        col = int(params["column"]) - 1
        row = int(params["row"]) - 1

        click_event = event = None

        # TBD: check for different buttons in press events and send combined button events
        if moving:
            event = Event(EventTypes.MouseMove, pos=V2(col, row), buttons=button)
        elif pressed:
            ts = time.time()
            event = Event(EventTypes.MousePress, pos=V2(col, row), buttons=button, time=ts)
            self.last_press = (ts, button,)
        else:
            ts = time.time()
            event = Event(EventTypes.MouseRelease, pos=V2(col, row), buttons=button)
            if ts - self.last_press[0] < self.CLICK_THRESHOLD and button == self.last_press[1]:
                Event(EventTypes.MouseClick, pos=V2(col, row), buttons=button, time=ts)
                if ts - self.last_click[0] < self.DOUBLE_CLICK_THRESHOLD and button == self.last_click[1]:
                    Event(EventTypes.MouseDoubleClick, pos=V2(col, row), buttons=button, time=ts)
                self.last_click = (ts, button,)

        return event

    def flush_clicks(self):
        to_kill = []
        for i, click in enumerate(self.on_hold_clicks):
            if click["time"] - time.time() > 0.1:
                Event(EventTypes.MouseClick, **click)
                to_kill.append(i)
        for index in reversed(to_kill):
            self.on_hold_clicks.pop(index)


    def __call__(self):
        # Keeps symmetry with "keyboard" which must be called for use as with context management
        return self


# Singleton avaliable application wide:
mouse = _Mouse()


if sys.platform != "win32":
    import fcntl
    import termios
    # Singleton avaliable application wide:
    keyboard = _PosixKeyboard()
    inkey = keyboard.inkey
    KeyCodes = _posix_KeyCodes
else:
    import msvcrt
    # Singleton avaliable application wide:
    keyboard = _WindowsKeyboard()
    inkey = keyboard.inkey
    KeyCodes = _win32_KeyCodes
