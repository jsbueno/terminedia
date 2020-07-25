from terminedia.unicode import split_graphemes, GraphemeIter

import pytest

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


def test_graphemeiter_iter_cooked_indexes():
    tilde = chr(0x303)
    cedilla = chr(0x327)
    grapheme = "a" + tilde + cedilla
    msg = grapheme + "b" + grapheme + "b"

    a = GraphemeIter(msg)
    assert list(a.iter_cooked_indexes([0, 3, 4])) == [0, 1, 2]
    assert list(a.iter_cooked_indexes(range(len(msg)))) == [0, 0, 0, 1, 2, 2, 2]


def test_graphemeiter_iter_cooked_indexes_past_string_end():
    tilde = chr(0x303)
    cedilla = chr(0x327)
    grapheme = "a" + tilde + cedilla
    msg = grapheme + "b" + grapheme + "b"

    a = GraphemeIter(msg)

    assert list (a.iter_cooked_indexes([8])) == []
    with pytest.raises(StopIteration):
        next(iter(a.iter_cooked_indexes([8])))
