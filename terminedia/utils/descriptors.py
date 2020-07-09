from weakref import WeakKeyDictionary, finalize


class LazyBindProperty:
    """Special Internal Use Descriptor

    This creates the associated attribute in an instance only when the attribute is
    acessed for the first time, in a dynamic way. This allows objcts such as Shapes
    have specialized associated "draw", "high", "text", "sprites" attributes,
    and still be able to be created lightweight for short uses that will use just
    a few, or none, of these attributes.
    """

    def __init__(self, initializer=None, type=None):
        self.type = type
        if not initializer:
            return
        self.initializer = initializer

    def __call__(self, initializer):
        self.initializer = initializer
        return self

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, instance, owner):
        from terminedia.image import ShapeView

        if not instance:
            return self
        if isinstance(instance, ShapeView):
            namespace = getattr(instance, "_" + self.name, None)
            if not namespace:
                namespace = self.initializer(instance)
                setattr(instance, "_" + self.name, namespace)
            return namespace
        if self.name not in instance.__dict__:
            instance.__dict__[self.name] = self.initializer(instance)
        return instance.__dict__[self.name]

    def __set__(self, instance, value):
        if self.type and not isinstance(value, self.type):
            raise AttributeError(
                f"{self.name!r} must be set to {self.type} instances on {instance.__class__.__name__} objects."
            )
        instance.__dict__[self.name] = value


class ObservableProperty:
    """This puts the "R' in Reactive
    """
    def __init__(self, fget=None, fset=None, fdel=None):
        """Change subscrible descriptor - enables Reactive/Observable  pattern

        Can work as the "property" decorator, and enable
        calls to be made to register callbacks on _instances_
        of the owner class. Whenever the guarded attribute
        is either read/written the callback is activated.

        Effective for linking properties eagerly.

        If called with no parameters, create guards to
        simply store/retrieve an attribute on the host instance's __dict__,
        """
        self.registry = WeakKeyDictionary()
        self.next_handler_id = 0
        self.callbacks = {}
        if fget is None:
            self._simple_storage()
            return
        self.fget = fget
        self.fset = fset
        self.fdel = fdel

    def __set_name__(self, owner, name):
        self.owner = owner
        self.name = name

    def _default_getter(self, instance):
        if self.name not in instance.__dict__:
            raise AttributeError(f"No attribute {self.name}")
        return instance.__dict__[self.name]

    def _default_setter(self, instance, value):
        instance.__dict__[self.name] = value

    def _default_deleter(self, instance):
        if self.name not in instance.__dict__:
            raise AttributeError(f"No attribute {self.name}")
        del instance.__dict__[self.name]

    def _simple_storage(self):

        self.fget = self._default_getter
        self.fset = self._default_setter
        self.fdel = self._default_deleter

    def setter(self, func):
        self.fset = func
        return self

    def deleter(self, func):
        self.fdel = func
        return self

    def __get__(self, instance, owner):
        if instance is None:
            return self
        value = self.fget(instance)
        if instance in self.registry:
            self.execute(instance, "get", value)
        return value

    def __set__(self, instance, value):
        self.fset(instance, value)
        if instance in self.registry:
            self.execute(instance, "set", value)
        return value

    def __delete__(self, instance):
        value = self.fdel(instance)
        if instance in self.registry:
            self.execute(instance, "del")
        return value

    def execute(self, instance, event, value=None):
        for target_event, handler in self.registry.get(instance, ()):
            if target_event == event and handler in self.callbacks:
                callback, args = self.callbacks[handler]
                callback(value, *args)

    def register(self, instance, event, callback, *args):
        handler = self.next_handler_id
        if instance not in self.registry:
            self.registry[instance] = []
        self.registry[instance].append((event, handler))
        self.callbacks[handler] = (callback, args)

        def eraser(self, id):
            if id in self.callbacks:
                del self.callbacks[id]

        finalize(instance, eraser, self, handler)
        self.next_handler_id += 1
        return handler

    def unregister(self, handler):
        if handler in self.callbacks:
            del self.callbacks[handler]
            return True
        return False

    def __repr__(self):
        return f"<{self.__class__.__name__} on {self.fget.__qualname__ if self.fget.__name__ != '<lambda>' else self.owner.__qualname__ + '.' + self.name} with {len(self.callbacks)} registered callbacks>"
