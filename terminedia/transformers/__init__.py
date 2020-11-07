from inspect import signature

from terminedia.utils import V2, HookList, get_current_tick
from terminedia.values import EMPTY, FULL_BLOCK, TRANSPARENT, Directions, Color

class Transformer:

    channels = "pixel char foreground background effects".split()

    for channel in channels:
        locals().__setitem__(channel, None)
    del channel

    def __init__(self, pixel=None, char=None, foreground=None, background=None, effects=None):
        """
        Class implementing a generic filter to be applied on an shape's pixels when their value is read.

        The parameters for __init__ are slots that will generate or transform the corresponding
        value on the final pixel

        Each slot can be None, a static value, or a callable.

        Each of these callables can have in the signature named parameters with any combination of

            "self, value, char, foreground, background, effects, pixel, pos, source, context, tick"
            Each of these named parameters will be injected as an argument when the
            it is called.
                - "self": Transformer instance (it is, as the others, optional)
                - "value": the current value for this channel
                - "char, foreground, background, effects": the content of the respective channel
                - "pos": the pixel position,
                - "pixel" meaning the source pixel as transformed to this point on the pipeline ,
                - "source" meaning
                    the whole source shape. The callable should be careful to read the shape
                    with "get_raw", and not using __getitem__ to avoid an infinite loop
                    (an evolution of this may give a 'transformed down to here' view
                    of the shape, or a 3x3 and 5x5 kernel options)
                - "tick" meaning the "frame number" from app start, and in the future
                    will be used for animations.

            Depending where the transformers are used, more input parameters may be available -
            they have to be set as instance attributes in the Transformer instance prior
            to rendering. For rich-text rendering embedded transformers
            (see terminedia.text.planes and terminedia.txt.sprites), for example,
            the following attribute are available:
                - "sequence_index": index of the current character inside the string
                    affected by the Transformer
                - "sequence_len": length of the string affected by the Transformer
                - "sequence": actual text spam affected by the Transformer
                - "sequence_absolute_start": index in  the text being rendered the transformer was made active

        It should return the value to be used downstream of the named channel.

        """
        self.signatures = {}
        for slotname in self.channels:
            # Build signature for channels defined in subclasses:
            self._build_signature(slotname)
            value = locals()[slotname]
            if value is not None:
                if slotname in ("foreground", "background") and not callable(value):
                    value = Color(value)
                setattr(self, slotname, value)

    def _build_signature(self, channel):
        self.signatures[channel] = frozenset(signature(getattr(self, channel)).parameters.keys()) if callable(getattr(self, channel)) else ()

    def __setattr__(self, attr, value):
        super().__setattr__(attr, value)
        if attr in self.__class__.channels:
            self._build_signature(attr)

    def __repr__(self):
        channel_list = []
        for channel_name in self.channels:
            channel = getattr(self, channel_name, None)
            if not channel:
                continue
            if callable(channel):
                channel_repr = "<{}>{}({})".format(
                    'method' if hasattr(channel, '__func__') else 'function',
                    channel.__name__,
                    ', '.join(sig for sig in self.signatures[channel_name])
                )
            else:
                channel_repr = repr(channel)
            channel_list.append((channel_name, channel_repr))

        return "{}({})".format(
            self.__class__.__name__,
            ", ".join(f"{name}={rpr}" for name, rpr in channel_list)
        )


class KernelTransformer(Transformer):
    policy = "abyss"

    def __init__(self, kernel, mask_diags=True, **kwargs):
        self.kernel = kernel
        self.mask_diags = mask_diags
        super().__init__(**kwargs)

    def kernel_match(self, source, pos):
        from terminedia.image import ImageShape
        source_is_image = False
        if  hasattr(source, "value_data"):
            data = source.value_data
            ...
            # TODO: 'fastpath' made faster for fullshapes
            value = ...
        elif isinstance(source, ImageShape):
            source_is_image = True
        else:
            data = source.data

        value = ""

        for y in -1, 0, 1:
            for x in -1, 0, 1:
                compare_pos = pos + (x, y)
                offset = source.get_data_offset(compare_pos)
                if offset is None:
                    if self.policy == "abyss":
                        value += " "
                    else:
                        raise NotImplementedError("Out of bound policy not implemented: {self.policy}")
                    continue
                if self.mask_diags and (x and y):
                    value += " "
                    continue

                if source_is_image:
                    value += "#" if source.get_raw(pos) != source.context.background else " "
                    continue
                value += "#" if data[offset] not in (EMPTY, TRANSPARENT) else " "

        return self.kernel.get(value, self.kernel.get("default", " "))

    def char(self, source, pos):
        return self.kernel_match(source, pos)


kernel_dilate = {
    "   "\
    "   "\
    "   ": " ",

    "default": FULL_BLOCK,
}

dilate_transformer = KernelTransformer(kernel_dilate)


class GradientTransformer(Transformer):

    def __init__(self, gradient, direction=Directions.RIGHT, size=None, channel="foreground", repeat="saw", **kwargs):
        """
        A Transformer that will take in a gradient object and return its value based on the position of each pixel

        Params:
          - gradient: The gradient to use. An instance of `terminedia.utils.Gradient`
                will work for the color channels. A custom object that will return
                the desired value when used with a value from 0 to 1 on __getitem__ can be
                used for non-color channels.
          - direction: The direction in which the gradient should flow
          - channel: To which channel apply the gradient. By default to "foreground", but
                can be "background", "effects", "char" and "pixel" (the last three
                will require a custom "gradient" object returning values of the appropriate type)
          - size: By default, the gradient size is adjusted to the width or height (depending on direction)
                of the source being transformed. Optionally the size can be constrained, and the gradient
                will be repeated from that point on. If a "scaled" gradient is passed and no size is given,
                the scale-factor of the gradient is used as size for the transformer.
          - repeat: the repeat mode for the gradient when the positin being printed is past its "size"


        """

        self.gradient=gradient
        self.direction = direction
        self.repeat = repeat
        self.channel = channel

        super().__init__(**{channel: self._engine})

    def h_rel_pos(self, source, pos):
        return pos.x / (source.width - 1)

    def v_rel_pos(self, source, pos):
        return pos.y / (source.height - 1)

    def _engine(self, source, pos):
        if self.direction == Directions.RIGHT:
            pos = self.h_rel_pos(source, pos)
        elif self.direction == Directions.LEFT:
            pos = 1 - self.h_rel_pos(source, pos)
        elif self.direction == Directions.DOWN:
            pos = self.v_rel_pos(source, pos)
        elif self.direction == Directions.UP:
            pos = 1 - self.v_rel_pos(source, pos)

        return self.gradient[pos]


class TransformersContainer(HookList):
    def __init__(self, *args):
        super().__init__(*args)

    stack = property(lambda s: s.data)


    def insert_hook(self, item):
        item = super().insert_hook(item)
        if not isinstance(item, Transformer):
            raise TypeError("Only Transformer instances can be added to a TransformersContainer")
        item.container = self
        return item

    def process(self, source, pos, pixel):
        """Called automatically by FullShape.__getitem__

        Only implemented for pixels with all attributes (used by fullshape)
        """
        pcls = type(pixel)
        values = list(pixel)

        def build_args(channel, signature):
            nonlocal transformer, pixel, values, ch_num
            args = {}
            for parameter in signature:
                if parameter == "self":
                    args["self"] = transformer
                elif parameter == "value":
                    args["value"] = values[ch_num]
                elif parameter in Transformer.channels and parameter != "pixel":
                    args[parameter] = getattr(pixel, parameter if parameter != "char" else "value")
                elif parameter == "pos":
                    args["pos"] = V2(pos)
                elif parameter == "pixel":
                    args["pixel"] = pixel
                elif parameter == "source":
                    args["source"] = source
                elif parameter == "tick":
                    args["tick"] = get_current_tick()
                elif parameter == "context":
                    args["context"] = source.context
                elif hasattr(transformer, parameter):
                    # Allows for custom parameters that can be made available
                    # for specific uses of transformers.
                    # (ex.: 'sequence_index' for transformers inlined in rich-text rendering)
                    args[parameter] = getattr(transformer, parameter)
            return args

        values = list(pixel)
        for transformer in self.stack:
            dest_values = values[:]
            for ch_num, channel in enumerate(Transformer.channels, -1):
                transformer_channel = getattr(transformer, channel, None)
                if transformer_channel is None:
                    continue
                if not callable(transformer_channel):
                    if ch_num == -1:  # (pixel channel)
                        continue
                    dest_values[ch_num] = transformer_channel
                    continue
                params = build_args(transformer_channel, transformer.signatures[channel])
                if ch_num == -1:  # (pixel channel)
                    dest_values = list(transformer_channel(**params))
                else:
                    dest_values[ch_num] = transformer_channel(**params)
            values = dest_values

        pixel = pcls(*values)
        return pixel

    def bake(self, shape, target=None, offset=(0, 0)):
        """Apply the transformation stack for each pixel in the given shape

        Args:
          - shape: Source shape object to be processed
          - target [Optional]: optional target where final pixels are blitted into.
                If target is not given, 'shape' is modified inplace. Defaults to None.
          - offset: pixel-offset to blit the data to. Most useful with the target
          option.

        Returns:
          the affected Shape object
        """
        from terminedia.image import FullShape

        if target:
            source = shape
        else:
            # Creates a copy of all data channels, sans sprites neither transformers:
            source = FullShape.promote(shape)
            target = shape

        # if target is shape, bad things will happen for some transformers - specially Kernel based transforms

        offset = V2(offset)
        for pos, pixel in source:
            target[pos + offset] = self.process(source, pos, pixel)
        return target

    def remove(self, tr):
        # override default remove for a safe "pass if not exist" (and faster)
        if tr in self.data:
            self.data.remove(tr)
