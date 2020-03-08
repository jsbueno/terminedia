
from terminedia.values import FULL_BLOCK

from .base import KernelTransformer
from .kernel_simple_lines import kernel as kernel_simple_lines


kernel_dilate = {
    "   "\
    "   "\
    "   ": " ",

    "default": FULL_BLOCK,
}

dilate_transformer = KernelTransformer(kernel_dilate)

ascii_lines_transformer = KernelTransformer(kernel_simple_lines, match_only=FULL_BLOCK)

__all__ = ["dilate_transformer", "ascii_lines_transformer"]
