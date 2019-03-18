import termios, fcntl, sys, os
import threading
import time
from contextlib import contextmanager

# Keyboard reading code copied and evolved from
# https://stackoverflow.com/a/6599441/108205
# (@mheyman, Mar, 2011)

@contextmanager
def realtime_keyb():
    """Waits for a single keypress on stdin.

    This is a silly function to call if you need to do it a lot because it has
    to store stdin's current setup, setup stdin for reading single keystrokes
    then read the single keystroke then revert stdin back after reading the
    keystroke.

    Returns a tuple of characters of the key that was pressed - on Linux,
    pressing keys like up arrow results in a sequence of characters. Returns
    ('\x03',) on KeyboardInterrupt which can happen when a signal gets
    handled.

    """
    fd = sys.stdin.fileno()
    # save old state
    flags_save = fcntl.fcntl(fd, fcntl.F_GETFL)
    attrs_save = termios.tcgetattr(fd)
    # make raw - the way to do this comes from the termios(3) man page.
    attrs = list(attrs_save) # copy the stored version to update
    # iflag
    attrs[0] &= ~(termios.IGNBRK | termios.BRKINT | termios.PARMRK
                  | termios.ISTRIP | termios.INLCR | termios. IGNCR
                  | termios.ICRNL | termios.IXON )
    # oflag
    attrs[1] &= ~termios.OPOST
    # cflag
    attrs[2] &= ~(termios.CSIZE | termios. PARENB)
    attrs[2] |= termios.CS8
    # lflag
    attrs[3] &= ~(termios.ECHONL | termios.ECHO | termios.ICANON
                  | termios.ISIG | termios.IEXTEN)
    termios.tcsetattr(fd, termios.TCSANOW, attrs)
    fcntl.fcntl(fd, fcntl.F_SETFL, flags_save | os.O_NONBLOCK)
    yield
    # restore old state
    termios.tcsetattr(fd, termios.TCSAFLUSH, attrs_save)
    fcntl.fcntl(fd, fcntl.F_SETFL, flags_save)


def inkey(break_=True):
    keycode = ""
    while True:
        c = sys.stdin.read(1) # returns a single character
        if not c:
            break
        if c == "\x03" and break_:
            raise KeyboardInterrupt
        keycode += c
    return keycode


def testkeys():
    with realtime_keyb():
        while True:
            try:
                key = inkey()
            except KeyboardInterrupt:
                break
            if key:
                print("", key.encode("utf-8"), end="", flush=True)
            print(".", end="", flush=True)
            time.sleep(0.3)



DEFAULT_BG = 0xfffe
DEFAULT_FG = 0xffff

class BlockChars:
    QUADRANT_UPPER_LEFT = '\u2598'
    QUADRANT_UPPER_RIGHT = '\u259D'
    UPPER_HALF_BLOCK = '\u2580'
    QUADRANT_LOWER_LEFT = '\u2596'
    LEFT_HALF_BLOCK = '\u258C'
    QUADRANT_UPPER_RIGHT_AND_LOWER_LEFT = '\u259E'
    QUADRANT_UPPER_LEFT_AND_UPPER_RIGHT_AND_LOWER_LEFT = '\u259B'
    QUADRANT_LOWER_RIGHT = '\u2597'
    QUADRANT_UPPER_LEFT_AND_LOWER_RIGHT = '\u259A'
    QUADRANT_UPPER_LEFT_AND_UPPER_RIGHT_AND_LOWER_RIGHT = '\u259C'
    LOWER_HALF_BLOCK = u'\2584'
    QUADRANT_UPPER_LEFT_AND_LOWER_LEFT_AND_LOWER_RIGHT = '\u2599'
    FULL_BLOCK = '\u2588'


class ScreenCommands:

    def print(self, *args, sep='', end='', flush=True):
        print(*args, sep=sep, end=end, flush=flush)

    def CSI(self, *args):
        command = args[-1]
        args = ';'.join(str(arg) for arg in args[:-1]) if args else ''
        self.print("\x1b[", args, command)

    def SGR(self, *args):
        self.CSI(*args, 'm')

    def clear(self):
        self.CSI(2, 'J')

    def moveto(self, pos):
        x, y = pos
        self.CSI(f'{y + 1};{x + 1}H')

    def print_at(self, pos, txt):
        self.moveto(pos)
        self.print(txt)

    def _normalize_color(self, color):
        if isinstance(color, int):
            return color
        if 0 <= color[0] < 1.0 or color[0] == 1.0 and all(lambda c: c <= 1.0, color[1:]):
            color = tuple(int(c * 255) for c in color)
        return color

    def reset_colors(self):
        self.SGR(0)

    def set_colors(self, foreground, background):
        if foreground == DEFAULT_FG:
            fg_seq = 39,
        else:
            foreground = self._normalize_color(foreground)
            fg_seq = 38, 2, *foreground
        if background == DEFAULT_BG:
            bg_seq = 49,
        else:
            background = self._normalize_color(background)
            bg_seq = 49, 2, *background

        self.SGR(*fg_seq, *bg_seq)

    def set_fg_color(self, color):
        color = self._normalize_color(color)
        self.SGR(38, 2, *color)

    def set_bg_color(self, color):
        color = self._normalize_color(color)
        self.SGR(48, 2, *color)


class Screen:
    lock = threading.Lock()

    def __init__(self, size=()):
        if not size:
            size = os.get_terminal_size()
        self.width, self.height = self.size = size

        self.local = threading.local()
        self.commands = ScreenCommands()
        self.clear(True)

    def clear(self, wet_run=True):
        self.data = [" "] * self.width * self.height
        self.color_data = [(DEFAULT_FG, DEFAULT_BG)] * self.width * self.height
        self.local.color = DEFAULT_FG
        self.local.background = DEFAULT_BG
        # To use when we allow custom chars along with blocks:
        # self.char_data = " " * self.width * self.height
        if wet_run:
            with self.lock:
                self.commands.clear()

    def set_at(self, pos, color=None):
        if color:
            self.local.color = color
        self[pos] = BlockChars.FULL_BLOCK

    def reset_at(self, pos):
        self[pos] = " "

    def __getitem__(self, pos):
        return self.data[pos[0] + pos[1] * self.width]

    def __setitem__(self, pos, value):
        index = pos[0] + pos[1] * self.width
        self.data[index] = value
        with self.lock:
            colors = self.local.color, self.local.background
            self.color_data[index] = colors
            self.commands.set_colors(*colors)
            self.commands.print_at(pos, value)


def main():
    scr = Screen()
    with realtime_keyb():
        for x in range(10, 30):
            scr.set_at((x, 10))
            scr.set_at((x, 20))
        for y in range(10, 21):
            scr.set_at((10, y))
            scr.set_at((29, y))

        scr[0, scr.height -1] = ' '
        while True:
            if inkey() == '\x1b':
                break
            time.sleep(0.05)


if __name__ == "__main__":
    # testkeys()
    main()
