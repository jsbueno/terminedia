import terminedia as TM

import pytest

@pytest.mark.parametrize(
    ("number_name", "text_name"),[
        (8, "block"),
        (4, "high"),
        ((8, 4), "square"),
        (2, "braille"),
        (1, "normal"),
])
def test_text_planes_aliases(number_name, text_name):
    # Both shape.text, and each plane are to be dynamically created
    # on first access.
    assert sh.text is sh.text
    sh = TM.shape((10, 10))
    assert sh.text[number_name] is sh.text[text_name]
