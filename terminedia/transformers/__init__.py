from inspect import signature

from terminedia.utils import V2, HookList, get_current_tick
from terminedia.values import EMPTY, FULL_BLOCK, Directions, Color

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
                    will be used for animations. It is currently injected as "0".

        It should return the value to be used downstream of the named channel.

        """
        for slotname in self.channels:
            value = locals()[slotname]
            if value is not None:
                if slotname in ("foreground", "background") and not callable(value):
                    value = Color(value)
                setattr(self, slotname, value)

        self.signatures = {
            channel: frozenset(signature(getattr(self, channel)).parameters.keys()) if callable(getattr(self, channel)) else () for channel in self.channels
        }


    def __repr__(self):
        return "Transformer <{}{}>".format(
            ", ".join(channel for channel in self.channels if getattr(self, channel + "_f", None)),
            f", source={self.source!r},  mode={self.mode!r}" if getattr(self, "source", None) else "",
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
                value += "#" if data[offset] != EMPTY else " "

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

    def __init__(self, gradient, direction=Directions.RIGHT, **kwargs):
        self.gradient=gradient
        self.direction = direction
        super().__init__(**kwargs)

    def h_rel_pos(self, source, pos):
        return pos.x / source.width

    def v_rel_pos(self, source, pos):
        return pos.y / source.height

    def foreground(self, source, pos):
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
        self.stack = self.data

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
