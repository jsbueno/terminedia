import pytest
import terminedia.image as IMG
import terminedia as TM
from terminedia.values import DEFAULT_FG, Directions as D

def test_palettedshape_new_works():

    a = IMG.PalettedShape.new((10,10))
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
    a = IMG.PalettedShape("...\n....")
    assert a.context.color == DEFAULT_FG

@pytest.mark.parametrize(
    "direction, quantity, exp_width, exp_height, exp_data".split(", "), [
    (D.RIGHT, 1, 6, 3, [255, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 128]),
    (D.LEFT, 1, 6, 3, [0, 0, 0, 255, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 128, 0, 0, 0]),
    (D.DOWN, 1, 3, 6, [255, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 128]),
    (D.UP, 1, 3, 6, [0, 0, 0, 0, 0, 0, 0, 0, 128, 255, 0, 0, 0, 0, 0, 0, 0, 0]),
    ((1, 1), 1, 6, 6, [255, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 128]),
    ((-1, -1), 1, 6, 6, [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 128, 0, 0, 0, 0, 0, 0, 255, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
    (D.RIGHT, 2, 9, 3, [255, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 128, 0, 0, 128]),
])
def test_valueshape_concat(direction, quantity, exp_width, exp_height, exp_data, DISPLAY, DELAY):
    a = IMG.ValueShape.new((3, 3), color=(0,0,0))
    b = IMG.ValueShape.new((3, 3), color=(0,0,0))

    a[0, 0] = (255,0,0)
    b[2, 2] = (128, 128, 255)
    c = a.concat(*((b,) * quantity), direction=direction)

    compare_data = [v[0] for v in c.data]

    if DISPLAY:
        with TM.Screen(clear_screen=True) as sc:
            sc.draw.blit((0,0), c)
            sc.context.color = (128, 128, 255)
            sc.print_at((0, 11), f"quantity={quantity}, width={c.width}, heigth={c.height}")
            sc.print_at((0, 10), f"{compare_data!r}")
            TM.pause(DELAY)


    assert c.width == exp_width
    assert c.height == exp_height
    assert  compare_data == exp_data
