from functools import wraps
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
        or on the owner class. Whenever the guarded attribute
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
        if instance in self.registry or owner in self.registry or self in self.registry:
            self.execute(instance, "get", value)
        return value

    def __set__(self, instance, value):
        self.fset(instance, value)
        if instance in self.registry or instance.__class__ in self.registry or self in self.registry:
            self.execute(instance, "set", value)
        return value

    def __delete__(self, instance):
        value = self.fdel(instance)
        if instance in self.registry or instance.__class__ in self.registry or self in self.registry:
            self.execute(instance, "del")
        return value

    def execute(self, instance, event, value=None):
        universal_events = self.registry.get(self, [])
        classwide_events = self.registry.get(instance.__class__, [])
        instance_events = self.registry.get(instance, [])
        for target_event, handler in universal_events + classwide_events + instance_events:
            if target_event == event and handler in self.callbacks:
                callback, args = self.callbacks[handler]
                callback(value, instance, *args)

    def register(self, instance, event, callback, *args):
        """Used to register a callback for an event involving this property in an instance

        Params:
          - instance: The instance of the host class that will trigger the callback
                Id instance is None, or the class itself, the callback
                    is set for _all_ instances in all subclasses of the owner class,
                    if instance is set to the owner class or a specific subclass,  events
                        are registered for all instances of that subclass
          - event: event type as string - one of: 'get', 'set', 'del'
          - callback: The callable that will be run each time the property is accessed.
            - the instance is passed as first positional parameter
            - for "set" events, the value set is passed as a positional parameter.
            - extra parameters should be passed in "args"
        """
        handler = self.next_handler_id
        if instance is None:
            instance = self
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



class ClassCache:
    """Entangled decorators to cache and control cache invalidation of methods and functions

    An instance of this will have a tripplet of decorators:
    @ClassCache.cached will attach a cache based on the input parameters of a
    method, similar to functools.lru_cache - and @ClassCache.cached_prop
    will create a cached property. @ClassCache.invalidate will mark
    a method so that, when it is called, the cached values for the
    methods and properties in the same instance is invalidated.

    So, expensive calculations based on certain states of the instance
    can be lazily calculated just once, when they are needed -
    and re-calculated if the state they rely on gets changed.
    """

    def __init__(self):
        self.instances = WeakKeyDictionary()
        self.cached_methods = {}


    def cached(self, func):
        @wraps(func)
        def wrapper(instance, *args, **kwargs):
            if instance not in self.instances:
                self.instances[instance] = {}
                self.instances[instance]["tick"] = -1

            tick = self.instances[instance]["tick"]

            index = func, args, tuple(kwargs.items())

            if index not in self.instances[instance] or self.instances[instance][index][0] < tick:
                result = func(instance, *args, **kwargs)
                self.instances[instance][index] = (tick, result)

            return self.instances[instance][index][1]
        return wrapper


    def invalidate(self, func):
        # NB: this invalidates the caches _After_ the decorated method is run.
        # a generic version of this "per_class_cache_factory" would
        # likely have the caches been invalidated _prior_ to the method being run
        # or have this configurable.
        @wraps(func)
        def wrapper(instance, *args, **kwargs):
            try:
                result = func(instance, *args, **kwargs)
            finally:
                if instance not in self.instances:
                    self.instances[instance] = {}
                    self.instances[instance]["tick"] = -1
                self.instances[instance]["tick"] += 1
            return result
        return wrapper

    def cached_prop(self, func):
        return property(self.cached(func))
