from itertools import chain
from pathlib import Path

import re

from .core import Widget
from .misc import Selector, VBox
from .text import Entry

MAX_PATH_SIZE = 512

class FileSelector(VBox):
    _fixed_size = True

    def __init__(
        self,
        parent,
        initial_name = "",
        folder=".",
        allow_new=True, pick_directory=False, filters=(),
        allow_create_folder=True,
        constrain_navigation=True,
        preferred_folders=(),
        size=None,
        border=True,
        callback=None,
        **kwargs,
    ):

        if size is None:
            size = parent.size - (2,2)

        super().__init__(parent, size=size, border=border, **kwargs)

        self.initial_folder = self.folder = folder
        self.allow_new = allow_new
        self.allow_create_folder = allow_create_folder
        self.constrain_navigation = constrain_navigation
        self.preferred_folders = preferred_folders
        self.callback = callback

        self.main_entry = Entry(self, width=self.size[0] - 2, enter_callback=self.complete, text_size=MAX_PATH_SIZE)
        self.add(self.main_entry)

        self.folder_entry = Entry(self, width=self.size[0] - 2, pos=(0,1), value=self.folder, text_size=MAX_PATH_SIZE)
        self.add(self.folder_entry)

        h = self.size[1]-4
        self.main_selector = Selector(parent=self, pos=(0,2), options=self._file_list(), callback=self._list_selected,
                                      min_height=h, max_height=h, min_width=self.size[0] - 2, border=True, align="left")
        self.add(self.main_selector)
        self._last_selected = None

    @property
    def can_move_to_parent(self):
        f =  Path(self.folder)
        if f.parent == f:
            return False
        if self.constrain_navigation and len(f.parts) <= len(Path(self.initial_folder).parts):
            return False
        return True

    def _file_list(self):
        folder = Path(self.folder)
        files = [(f"[[{path.name}]]" if path.is_dir() else path.name, Path(path.name)) for path in sorted(
                chain(
                    (Path(".."),) if self.can_move_to_parent else (),
                    folder.iterdir() ),
                key = lambda path: (-path.is_dir(), str(path).upper())
                )]
        return files

    def _default_enter(self):
        self.complete()

    def _list_selected(self, selector, event=None):
        value = selector.value
        if str(value) == "..":
            if not self.can_move_to_parent:
                return
            value = Path(self.folder)
            if str(value) == ".": # len(value.parts) <= 1:
                value = value.absolute()
            value = value.parent
            self.folder = value
        elif (self.folder / value).is_dir():
            self.folder = str(Path(self.folder) / value)
        else:
            value = str(value)
            if value == self._last_selected and value == self.main_entry.value:
                return self.complete()
        self._update(value)
        self._last_selected = value

    def _update(self, value):
        if str(value) == "..":
            if not self.can_move_to_parent:
                return
        if str(self.folder) != self.folder_entry.value:
            self.main_selector.load_options(self._file_list())
        else:
            self.main_entry.value = value
        self.folder_entry.value = str(self.folder)

    @property
    def value(self):
        return Path(self.folder_entry.value) / self.main_entry.value

    def complete(self, widget=None, event=None):
        if self.callback:
            self.callback(self.value)
        self.done = True
        self.kill()




