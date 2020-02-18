"""Painting context related classes and utility funcions
"""
import threading
from copy import copy
from types import FunctionType

from terminedia.utils import Color, SpecialColor, V2
from terminedia.transformers import TransformersContainer
from terminedia.subpixels import BlockChars
from terminedia.values import DEFAULT_BG, DEFAULT_FG, Directions, Effects


_sentinel = object()


class ContextVar:
    def __init__(self, type_, default=None):
        self.type = type_
        self.default = default

    def __set_name__(self, owner, name):
        self.name = name

    def __set__(self, instance, value):
        if getattr(instance._locals, "_context_stack", None):
            return setattr(instance._locals._context_stack[-1], self.name, value)
        if not isinstance(value, self.type):
            # May generate ValueError TypeError: expected behavior
            type_ = self.type[0] if isinstance(self.type, tuple) else self.type
            value = type_(value)
        setattr(instance._locals, self.name, value)

    def __get__(self, instance, owner):
        if not instance:
            return self
        if getattr(instance._locals, "_context_stack", None):
            return getattr(instance._locals._context_stack[-1], self.name)
        value = getattr(instance._locals, self.name, _sentinel)
        if value is _sentinel:
            value = self.default
            if callable(value):
                value = value()
            setattr(instance._locals, self.name, value)
        return value


_EmptySentinel = object()


class Context:
    """Context class for Screen and Shape objects. Instances should live as ".context" on those

        Args:
        - **kw: initial keyword arguments for a context

        The drawing and printing operations on terminedia will
        set a graphic element on a target. Depending on the
        function it will either write an arbitrary character
        or just set/reset a pixel in the desired color.

        All the other attributes for the element being drawn are picked from
        its ".context" attribute which is an instance of this.

        The attributes here are set independently for each thread,
        and these are the ones currently used by the drawing functions:

        - color: color special value or RGB sequence for foreground color - either int 0-255  or float 0-1 based.
        - background: color special value or RGB sequence sequence for background color
        - direction: terminedia.Directions Enum value with writting direction
        - effects: terminedia.Effects Enum value with combination of text effects
        - char: Char to be plotted when setting a single color.
        - transformer: Callback that will change in-place each attribute of
        a graphic element immediately before actually setting then on the target.

        Also, if used as a context-manager, this pushes all current attributes in a stack,
        providing a practical way for a sub-routine to draw things
        to the target without messing with the callee's expected drawing context.
        Otherwise one would have to manually save and restore
        the context colors for each operation.  When entering
        a Context as a context manager, the original attributes are
        retained, but any changes to it in the corresponding `with` block
        are reverted on `__exit__`.
    """

    char = ContextVar((str, SpecialColor), BlockChars.FULL_BLOCK)
    color = ContextVar(Color, DEFAULT_FG)
    background = ContextVar(Color, DEFAULT_BG)
    effects = ContextVar((Effects, SpecialColor), Effects.none)
    direction = ContextVar(V2, Directions.RIGHT)
    transformers = ContextVar(TransformersContainer, None)
    fill = ContextVar(bool, False)
    font = ContextVar(str, "")

    def __init__(self, **kw):
        self._locals = threading.local()
        self._update_from_global()
        self.transformers = TransformersContainer()
        self._update(kw)
        self._dirty = False

    def _update(self, params):
        for attr, value in params.items():
            if attr.startswith("local_storage"):
                # not to be updated on __exit__
                continue
            setattr(self, attr, value)

    def __setattr__(self, name, value):
        if name.startswith("_"):
            return super().__setattr__(name, value)

        if getattr(self._locals, "_context_stack", None):
            return setattr(self._locals._context_stack[-1], name, value)

        if getattr(self.__class__, name, None):
            # Use descriptor
            super().__setattr__(name, value)
        else:
            self._dirty = True
            setattr(self._locals, name, value)

    def __getattr__(self, name):
        if getattr(self._locals, "_context_stack", None):
            return getattr(self._locals._context_stack[-1], name)
        return getattr(self._locals, name)

    def __call__(self, **kw):
        """Update new parameters before Context is used as a context manager"""
        self._locals._new_parameters = kw
        return self

    def __enter__(self):
        new_parameters = self._locals.__dict__.pop("_new_parameters", {})
        data = copy(self._locals.__dict__)
        data["_previously_existing"] = set(data.keys())
        self._locals.__dict__.setdefault("_stack", []).append(data)
        if "context" in new_parameters:
            self._locals.__dict__.setdefault("_context_stack", []).append(new_parameters.pop("context"))
            # Use this to signal that the stacked context should be popped on exit:
            self._locals._stack.append(_EmptySentinel)
        self._update(new_parameters)
        return self

    def __exit__(self, exc_name, traceback, frame):
        data = self._locals._stack.pop()
        if data is _EmptySentinel:
            self._locals._context_stack.pop()
            data = self._locals._stack.pop()

        to_remove = set(self._locals.__dict__.keys()) - data.pop("_previously_existing", set())
        for extra_key in to_remove:
            # .text shape namespaces have to persist data in the parent's context,
            # which may be in a context-manager (with) block due to
            # 'mundane' attribute settings.
            if extra_key.startswith("local_storage"):
                continue
            delattr(self._locals, extra_key)
        self._update(data)

    def __repr__(self):
        return "Context[\n{}\n]".format(
            "\n".join(f"   {key} = {value!r}" for key, value in self)
        )

    def __iter__(self):
        seen = set()
        for attr_name in dir(self):
            if attr_name.startswith("_"):
                continue
            seen.add(attr_name)
            yield (attr_name, getattr(self, attr_name))
        for attr_name in dir(self._locals):
            if attr_name.startswith("_") or attr_name in seen:
                continue
            yield (attr_name, getattr(self._locals, attr_name))

    def _update_from_global(self):
        import terminedia

        if not hasattr(terminedia, "context"):
            # global initialization not complete - we may be initializing the root context itself
            return
        for name, attr in terminedia.context:
            if name in ("default_bg", "default_fg", "transformers"):
                continue
            setattr(self, name, attr)

    def __dir__(self):
        if getattr(self._locals, "_context_stack", None):
            return dir(self._locals._context_stack[-1])
        return sorted(set(super().__dir__() + list(self._locals.__dict__.keys())))


class _RootContext(Context):
    """Internal Use - provide the default context values for the application.

    This is meant to be used as a Singleton - that is instantiated when the library
    is first imported and lives on as "terminedia.context".
    The main difference for ordinary contexts is that it is the authoritative source for
    the colors to be used as "DEFAULT_BG" and "DEFAULT_FG" on non-ANSI backends.
    ANSI backends have default values supplied by the terminal-emulator program itself,
    which can't be easily guessed by running applications. (Like White or Green foreground
    and Black background, depending on the terminal theme).


    """
    interactive_mode = ContextVar(bool, False)

    def __init__(self, default_fg, default_bg, **kwargs):
        super().__init__(**kwargs)
        # These are ordinary instance parameters, but are used as the default
        # source for components for "DEFAULT_FG" and "DEFAULT_BG" colors
        # for all non-terminal backends.
        self._default_fg = Color(default_fg)
        self._default_bg = Color(default_bg)

    # These dummy properties bypass the __setattr__ code in the superclass
    @property
    def default_fg(self):
        return self._default_fg

    @default_fg.setter
    def default_fg(self, value):
        from terminedia.values import DEFAULT_FG

        if value is DEFAULT_FG:
            raise ValueError("The source for default_fg can't be set as DEFAULT_FG")
        self._default_fg = Color(value)

    @property
    def default_bg(self):
        return self._default_bg

    @default_bg.setter
    def default_bg(self, value):
        from terminedia.values import DEFAULT_BG

        if value is DEFAULT_BG:
            raise ValueError("The source for default_bg can't be set as DEFAULT_BG")
        self._default_bg = Color(value)
