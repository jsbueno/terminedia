import threading

from collections.abc import MutableSequence, MutableMapping, Iterable, Mapping, Sequence
from copy import copy
from enum import IntFlag, EnumMeta


def mirror_dict(dct):
    """Creates a new dictionary exchanging values for keys
    Args:
      - dct (mapping): Dictionary to be inverted
    """
    return {value: key for key, value in dct.items()}


class FrozenDict(dict):
    """Quick hack for a hashable dict which could be used as key in a cache dictionary.

    If one needs this for real, please fill in a feature request
    on jsbueno/extradict. (You might use this, fix whatever is missing, and
    add a PR with that :-) )
    """
    __slots__ = ()
    __setitem__ = None

    def __setitem__(self, *args, **kw):
        raise NotImplementedError()

    update = setdefault = clear = pop = popitem = __delitem__ = __setitem__

    def __hash__(self):
        return hash(frozenset(self.items()))

    def __repr__(self):
        return f"{self.__class__.__name__}({super().__repr__()})"


class HookList(MutableSequence):
    def __init__(self, initial=()):
        self.data = list()
        for item in initial:
            self.append(item)

    def insert_hook(self, item):
        return item

    def __getitem__(self, index):
        return self.data[index]

    def __setitem__(self, index, item):
        item = self.insert_hook(item)
        self.data[index] = item

    def __delitem__(self, index):
        del self.data[index]

    def __len__(self):
        return len(self.data)

    def insert(self, index, item):
        item = self.insert_hook(item)
        self.data.insert(index, item)

    def __eq__(self, other):
        # why is not this free with MutableSequence? (posted on python-ideas, 2020-6-30)
        if not isinstance(other, type(self)):
            return NotImplemented
            # code corrected by suggestion of Serhiy Storchaka on Python-ideas
        return self.data == other.data

    def __copy__(self):
        cls = type(self)
        new = cls.__new__(cls)
        new.data = copy(self.data)
        return new

    def copy(self):
        return copy(self)

    def __repr__(self):
        return f"{self.__class__.__name__}({self.data!r})"


class TaggedDict(MutableMapping):
    """Mapping that allows key/value pairs to have attached tags

    when using the tags in browsing (values, keys), a tag may be specifed
    to filter out any pairs that do not have the same tag.

    How it works: When creating an item, if the key is a tuple,
    all components are considered "tags" - on retrieving an item,
    any tag will retrieve a collection of all itens with that tag.

    Special set funcionality applies to allow retrieving by more than
    one tag as an "and" operation.

    Also, for temporary working of a subset of the contents, say,
    all items that have the "animal" tag, one can call the ".view" with
    the desired tags - the view will point to the original data,
    but only make visible the itens with the requested tags.
    Items added to the view will have the view tags applied. Items
    added with the ".add" method instead of the `x[y] = z` mapping
    syntax will be added to a unique handle id, and associated
    with the current view tags. (the unique id is unique within
    the parent mapping)

    """
    # TODO: move this to "extradict" package and make a new release

    def __init__(self, initial_contents: Mapping = None):
        self.data = {}
        self._keys = {}
        self._filtering_keys = set()
        self._lock = threading.Lock()
        self._counter = [0]
        if initial_contents:
            self.update(initial_contents)

    def view(self, keys):
        cls = self.__class__
        new = cls.__new__(cls)
        new.data = self.data
        new._lock = self._lock
        new._keys = self._keys
        new._filtering_keys = self._get_local_keys(keys)
        new._counter = self._counter
        return new

    def _get_local_keys(self, keys):
        if not isinstance(keys, Iterable) or isinstance(keys, str):
            keys = {keys, }
        return frozenset((*self._filtering_keys, *keys))

    def __setitem__(self, keys, value):
        keys = self._get_local_keys(keys)
        with self._lock:
            self.data[keys] = value
            for key in keys:
                self._keys.setdefault(key, set()).add(keys)
            self._counter[0] += 1

    def _get_resolved_keys(self, keys):
        keys = self._get_local_keys(keys)
        if keys:

            keysets = [self._keys[key] for key in keys if key in self._keys]
            if len(keysets) < len(keys):
                unknown = set()
                for key in keys:
                    if key not in self._keys and key not in self._filtering_keys:
                        unknown.add(key)
                if unknown:
                    raise KeyError(repr(unknown))

            keysets = iter(keysets)
            resolved_keys = next(keysets, set())
            for keyset in keysets:
                resolved_keys = resolved_keys.intersection(keyset)
        else:
            resolved_keys = set(self.data.keys())
        return resolved_keys

    def __getitem__(self, keys):
        result = [self.data[keys] for keys in self._get_resolved_keys(keys)]
        if not result:
            raise KeyError(repr(keys))
        return result

    def __delitem__(self, keys):
        keys = self._get_local_keys(keys)
        with self._lock:
            for outter_key in keys:
                to_remove = set()
                for inner_key in self._keys[outter_key]:
                    if outter_key in inner_key:
                        to_remove.add(inner_key)
                self._keys[outter_key] -= to_remove
                if not self._keys[outter_key]:
                    del self._keys[outter_key]
            for key in self._get_resolved_keys(()):
                del self.data[key]

    def add(self, value):
        """Creates a unique tag for an item and add it in the current view

        Allows items to be added under selected tags under a view,
        without having to worry about unique identifiers within those tags

        Returns the unique key attributed to the item.
        """
        key = f"_id_{self._counter[0]}"
        self[key] = value
        return key

    def remove(self, value):
        key = sentinel = object()
        for key, other_value in self.items():
            if other_value == value:
                break
        else:
            if key is not sentinel:
                del self[key]
                return
        raise ValueError("Value not in TaggedDict")

    def __iter__(self):
        return iter(self._get_resolved_keys(()))

    def __len__(self):
        return len(self._get_resolved_keys(()))

    def values(self):
        return [item[0] for item in super().values()]

    def __repr__(self):
        result = "TaggedDict({{{}}})".format(", ".join(f"{tuple(key)}:{value!r}" for key, value in self.items()))
        if self._filtering_keys:
            result += "view({})".format(", ".join(repr(key) for key in self._filtering_keys))
        return result


class LazyDict(MutableMapping):
    """Dictionary whose items can be set to a callable that works as a factory of the actual value

    This exists so that some objects which values can be expensive to create are not instantiated
    at load time.

    As a convenience, values can be retrieved as attributes as well as by item-getting,
    so these Dicts can work somewhat like a namespace.
    """

    def __init__(self, *args, **kw):
        self.data = dict(*args, **kw)

    def __getitem__(self, key):
        item = self.data[key]
        if callable(item):
            item = item()
            self.data[key] = item
        return item

    __setitem__ = lambda self, key, value: self.data.__setitem__(key, value)
    __delitem__ = lambda self, key: self.data.__setitem__(key)
    __len__ = lambda self: len(self.data)
    __iter__ = lambda self: iter(self.data)

    def __getattr__(self, attr):
        if attr in self.data:
            return self[attr]
        raise AttributeError(attr)

    def __dir__(self):
        return sorted(super().__dir__() + list(self.keys()))

    def __repr__(self):
        return f"{self.__class__.__name__}({self.data!r})"


class Grapheme2DArray:
    """[WIP] This may evolve to replace the use of lists
    at the core of Shape objects
    """

    wordsize = 4
    encoding = "utf_32_le"

    def __init__(self, size, encoding=None):
        from terminedia.utils.vector import V2
        from terminedia.values import EMPTY

        if encoding is not None:
            self.encoding = encoding

        self.size = V2(size)
        self.linear_size = size[0] * size[1]

        self.data = bytearray(EMPTY.encode(self.encoding) * self.linear_size)

    def __getitem__(self, index):
        rindex = (index[1] * self.size[0] + index[0]) * 4
        return self.data[rindex: rindex + self.wordsize].decode(self.encoding)

    def __setitem__(self, index, item):
        rindex = (index[1] * self.size[0] + index[0]) * 4
        self.data[rindex: rindex + self.wordsize] = item.encode(self.encoding)

    def __delitem__(self, index):
        from terminedia.values import EMPTY
        self.__setitem__(index, EMPTY)

    def __repr__(self):
        return f"{self.__class__.__name__}({tuple(self.size)!r})"



class IterableFlag(IntFlag):
    def __iter__(self):
        """much hacky. very smart: composed flags are now iterable!"""
        for element in self.__class__:
            if self & element:
                yield element

    def __contains__(self, element):
        """if self is a group of various flags ored together, this returns if 'effect' is contained in then"""
        if not isinstance(element, self.__class__):
            return False
        return self & element

    def __len__(self):
        x = self.value
        count = 0
        while x:
            count += x % 2
            x >> 1
        return count

    def __add__(self, other):
        return self | other

    def __sub__(self, other):
        cls = self.__class__
        other = max(self.__class__) * 2 - 1 - (other.value if isinstance(other, cls) else other)
        return self & other


def _norm(string):
    return string.strip().lower().replace(" ", "_")



class OrableByNameEnumMixin:

    def __or__(self, other):
        if isinstance(other, (str, Sequence)) and not isinstance(other, type(self)):
            other = type(self)(other)
        return super().__or__(other)



class RetrieveFromNameEnumMeta(EnumMeta):
    def __call__(cls, val, *args, **kw):
        if val and not args and not kw and isinstance(val, (str, Sequence)) and not isinstance(val, cls):
            if isinstance(val, str) and "|" in val:
                val = [v for v in val.split("|")]
            elif isinstance(val, str):
                val = [val]
            val = [_norm(v) for v in val]
            final_val = 0
            for v in val:
                if isinstance(v, cls):
                    final_val |= v
                    continue
                final_val |= cls.__members__[v]
            return final_val
        return super().__call__(val, *args, **kw)


