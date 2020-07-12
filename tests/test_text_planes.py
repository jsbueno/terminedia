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
    sh = TM.shape((10, 10))
    assert sh.text is sh.text
    assert sh.text[number_name] is sh.text[text_name]


def test_text_plane_clear():
    sh = TM.shape((10, 10))
    sh.text[1].marks[1, 0] = TM.Mark(attributes={"color": TM.Color("yellow")})
    sh.text[1][0,0] = "qazwsx"
    assert isinstance(sh.text[1].marks[10,0], TM.Mark)
    assert sh.text[1].plane[1, 0] == "a"
    sh.text[1].clear()
    assert isinstance(sh.text[1].marks[10,0], TM.Mark)
    assert sh.text[1].plane[1, 0] == " "
    assert sh.text[1].marks.get((1, 0), None) is None
