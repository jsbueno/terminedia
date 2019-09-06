import pytest
import terminedia.image as IMG
from terminedia.values import DEFAULT_FG


def test_palettedshape_new_works():

    a = IMG.PalletedShape.new((10,10))
    a[5,5] = "A"
    assert a.data[10 * 5 + 5] == "A"
    assert a.data.count(" ") == 99


def test_valueshape_new_works():
    a = IMG.ValueShape.new((10,10))
    a[5,5] = (255, 255, 255)
    assert a.data[10 * 5 + 5] == (255, 255, 255)
    assert a.data.count((0, 0, 0)) == 99

def test_valueshape_new_works_grey():
    a = IMG.ValueShape.new((10,10), color=128)
    a[5,5] = 255
    assert a.data[10 * 5 + 5] == 255
    assert a.data.count(128) == 99


def test_imageshape_new_works():
    a = IMG.ImageShape.new((10,10), color=(128, 128, 128))
    a[5,5] = (255, 255, 255)
    assert a.data.getpixel((0, 0)) == (128, 128, 128)
    assert a.data.getpixel((5, 5)) == (255, 255, 255)


def test_shape_context_works():
    a = IMG.PalletedShape("...\n....")
    assert a.context.color == DEFAULT_FG
