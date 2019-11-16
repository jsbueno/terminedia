from collections import UserList
from inspect import signature

from terminedia.utils import V2, Spatial


class Transformer:

    channels = "char foreground background effects".split()

    def __init__(self, char=None, foreground=None, background=None, effects=None, spatial=None, source=None, mode="normal"):
        """
        Each slot can be None, a static value, or a callable.

        Each of these callables can have in the signature named parameters with any combination of

            "self, value, char, foreground, background, effects, pixel, pos, source, context, tick"
            Each of these named parameters will be injected as an argument when the
            function is called.
                - "self": Transformer instance (it is, as the others, optional)
                - "char, foreground, background, effects": the content of the respective channel
                - "pos": the pixel position,
                - "pixel" meaning the source pixel as transformed to this point on the pipeline ,
                - "source" meaning
                    the whole source shape. The callable should be careful to read the shape
                    with "get_raw", and not using __getitem__ to avoid an infinite loop
                    (an evolution of this may give a 'transformed down to here' view
                    of the shape, or a 3x3 and 5x5 kernel options)
                - "tick" meaning the "frame number" from app start, and in the future
                    will be used for animations. It is currently injected as "0".

        It should return the value to be used downstream of the named channel.

        """
        self.char = char
        self.foreground = foreground
        self.background = background
        self.effects = effects
        self.spatial = spatial
        self.source = source
        self.mode = mode

        self.signatures = {
            channel: frozenset(signature(getattr(self, channel)).parameters.keys()) if getattr(self, channel) else () for channel in self.channels
        }


    def __repr__(self):
        return "Transformer <{}{}>".format(
            ", ".join(channel for channel in self.channels if getattr(self, channel + "_f", None)),
            f", source={self.source!r},  mode={self.mode!r}" if self.source else "",
        )


class TransformersContainer(UserList):
    def __init__(self, *args):
        super().__init__(*args)
        self.stack = self.data

    def _init_item(self, item):
        if not isinstance(item, Transformer):
            raise TypeError("Only Transformer instances can be added to a TransformersContainer")
        item.container = self

    def __setitem__(self, index, item):
        self._init_item(item)
        super().__setitem__(index, item)

    def insert(index, item):
        self._init_item(item)
        super().insert(index, item)

    def process(self, source,):
        pass


"""
Doc string of old-style "transform-on-write" 'create_transformer'  - kept transitionally
due to the examples and ideas for transformers.



    ex. to install a transformer to force all text effects off:
    ```
    from terminedia values import create_transformer, NOP, Effects
    ...
    create_transformer(shape.context, [NOP, NOP, NOP, Effects.none])
    ```

    For a transformer that will force all color rendering
    to be done to the background instead of foreground:
    ```
    create_transformer(shape.context, [NOP, TRANSPARENT, lambda pos, values, context: values[1], NOP])
    ```

    Transfomer to make all printed numbers be printed blinking:

    ```
    create_transformer(shape.context, [NOP, NOP, NOP, lambda pos, values, context: Effects.blink if values[0].isdigit() else TRANSPARENT])
    ```



"""
