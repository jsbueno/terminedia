from pathlib import Path

import re

from .core import Widget
from .misc import Selector, VBox
from .text import Entry

class FileSelector(VBox):
    _fixed_size = True

    def __init__(
        self,
        parent,
        initial_name = "",
        folder=".",
        allow_new=True, pick_directory=False, filters=(),
        allow_create_folder=True,
        constrain_navigation=False,
        preferred_folders=(),
        size=None,
        border=True,
        callback=None,
        **kwargs,
    ):

        if size is None:
            size = parent.size - (2,2)


        super().__init__(parent, size=size, border=border, **kwargs)

        self.folder = folder
        self.allow_new = allow_new
        self.allow_create_folder = allow_create_folder
        self.constrain_navigation = constrain_navigation
        self.preferred_folders = preferred_folders
        self.callback = callback

        self.main_entry = Entry(self, width=self.size[0] - 2, enter_callback=self.complete)
        self.add(self.main_entry)
        h = self.size[1]-4
        files = list(map(str, Path(folder).iterdir()))
        self.main_selector = Selector(parent=self, pos=(0,2), options=files, callback=self._list_selected,
                                      min_height=h, max_height=h, min_width=self.size[0] - 2, border=True, align="left")
        self.add(self.main_selector)

    def _default_enter(self):
        self.complete()

    def _list_selected(self, selector, event=None):
        self.main_entry.value = str(selector.value)

    @property
    def value(self):
        return Path(self.main_entry.value)

    def complete(self, widget=None, event=None):
        if self.callback:
            self.callback(self.value)
        self.done = True
        self.kill()




