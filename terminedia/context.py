"""Painting context related classes and utility funcions
"""
import threading
from types import FunctionType

from terminedia.utils import Color, V2
from terminedia.values import DEFAULT_BG, DEFAULT_FG, BlockChars, Directions, Effects


_sentinel = object()


class Transformer:
    pass


class ContextVar:
    def __init__(self, type, default=None):
        self.type = type
        self.default = default

    def __set_name__(self, owner, name):
        self.name = name

    def __set__(self, instance, value):
        if not isinstance(value, self.type):
            # May generate ValueError TypeError: expected behavior
            type = self.type[0] if isinstance(self.type, tuple) else self.type
            value = type(value)
        setattr(instance._locals, self.name, value)

    def __get__(self, instance, owner):
        if not instance:
            return self
        value = getattr(instance._locals, self.name, _sentinel)
        if value is _sentinel:
            value=self.default
            if callable(value):
                value = value()
            setattr(instance._locals, self.name, value)
        return value


class Context:

    char = ContextVar(str, BlockChars.FULL_BLOCK)
    color = ContextVar((tuple, Color, int), DEFAULT_FG)
    background = ContextVar((tuple, Color, int), DEFAULT_BG)
    effects = ContextVar(Effects, Effects.none)
    direction = ContextVar(V2, Directions.RIGHT)
    transformer = ContextVar((Transformer, FunctionType, type(None)), None)


    def __init__(self, **kw):
        self._locals = threading.local()
        for attr, value in kw.items():
            setattr(self, attr, value)

    def __setattr__(self, name, value):
        if name.startswith("_") or getattr(self.__class__, name, None):
            super().__setattr__(name, value)
        else:
            setattr(self._locals, name, value)

    def __getattr__(self, name):
        return getattr(self._locals, name)

    def __repr__(self):
        return "Context[\n{}\n]".format("\n".join(
            f"   {key} = {getattr(self._locals, key)!r}" for key in dir(self._locals)
            if not key.startswith("_")
        ))
