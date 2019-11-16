from collections import UserList


class Spatial:
    def __init__(self):
        self.data = [
            1, 0, 0,
            0, 1, 0,
            0, 0, 1,
        ]
        self.is_identity = True


class Transformer:
    def __init__(self, char=None, foreground=None, background=None, effects=None, spatial=None, source=None, mode="normal"):
        """
        Each slot can be None, a static value, or a callable.

        Each of these callables have the signature:
            pos: V2, values: Union[Char, Color, Effects], context: Context, source: Shape

        It should return the value

        """
        self.char_s = char
        self.foreground_f = foreground
        self.background_f = background
        self.effects_f = effects
        self.spatial = spatial
        self.source = source
        self.mode = mode

        self.container = None


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


def create_transformer(context, slots, clear=False):
    """
    DEPRECATED - use the "Transformer" class instead.
    (this will be removed in a few commits - transformers are becoming a lazy "on read" action,
    instead of "on write")
    Attach a specialized callable to a drawing context to transform pixel values during rendering

    Args:
      - context (Drawing context namespace): the context
      - slots (Optional[Union[Constant, Callable[pos, values, context]]]): a sequence of callables that will perform the transform on each channel.
      - clear (bool): if True will replace existing transformers.
                      if False, the new transformation will be appended to the existing transformations in
                      the context.

      The callables passed to "slots" receive the full Pixel values as a sequence
      (for full capability pixels: char, foreground, background, text effects).
      Each callable have to return the final constant that will be applied as
      that component on the drawing target data.

      If one member of "slots" is not callable, it self is used
      as a constant for that channel. The special value `NOP`
      (``terminedia.values.NOP`` means no change to that channel.)

      Slot callables can return the special  `TRANSPARENT` constant to
      indicate the target value at the corresponding plane is preserved.

      Having fewer slots than are planes in the drawing context, means the
      remaining planes are left empty.

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

      To uninstall a transformer, just set it to `None`
      (that is: `shape.context.transformer = None`) or call this with slots=None.

      # TODO -make transformer into a class that allows post-creation introspection and manipulation

    """
    from terminedia.values import NOP

    if not slots:
        context.transformer = None
        return

    previous_transformer = getattr(context, "transformer", None)
    if clear:
        previous_transformer = None

    def transformer(pos, values):
        if previous_transformer:
            values = previous_transformer(pos, values)
        return [
            slot(pos, values, context)
            if callable(slot)
            else slot
            if slot is not NOP
            else values[i]
            for i, slot in enumerate(slots)
        ]

    context.transformer = transformer

