from terminedia.unicode import split_graphemes, GraphemeIter

def test_split_grapheme_works():
    tilde = chr(0x303)
    cedilla = chr(0x327)
    grapheme = "a" + tilde + cedilla
    msg = grapheme + "b" + grapheme

    a = split_graphemes(msg)
    assert len(a) == 3
    assert a[0] == grapheme
    assert a[1] == "b"
    assert a[2] == grapheme


def test_graphemeiter_works():
    tilde = chr(0x303)
    cedilla = chr(0x327)
    grapheme = "a" + tilde + cedilla
    msg = grapheme + "b" + grapheme

    a = GraphemeIter(msg)
    assert len(a) == 3
    b = iter(a)
    assert next(b) == grapheme
    assert next(b) == "b"
    assert next(b) == grapheme
