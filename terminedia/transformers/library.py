from . import Transformer, KernelTransformer
from ._kernel_table_ascii import kernel as kernel_table_ascii

ascii_table_transformer = KernelTransformer(kernel_table_ascii)



del Transformer, KernelTransformer, kernel_table_ascii

