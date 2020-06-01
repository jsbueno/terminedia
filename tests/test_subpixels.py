import pytest
import terminedia.image as IMG
import terminedia as TM
from terminedia.values import DEFAULT_FG, Directions as D

from conftest import rendering_test, fast_and_slow_render_mark

# ==============================================================================================
# The heuristics for the HalfBlock full color, with random pixel access is weird!
# So we better have verbose fine grained tests on both the final result on the square resolution
# And on how those are represented in the coarser-grained character block
# ==============================================================================================

@pytest.mark.parametrize(*fast_and_slow_render_mark)
@rendering_test
def test_square_fullcolor_sets_pixel():

    sc = TM.Screen(size=(3, 3))
    sc.data.square.set_at((0,0))
    sc.update((0, 0))
    yield None  # Uncomment along with decorators to enable 'visual display' of test-output
    assert sc.data.square.get_at((0,0)) is TM.DEFAULT_FG
    assert sc.data.square.get_at((0,1)) is TM.DEFAULT_BG
    assert sc.data[0,0].value == TM.subpixels.HalfChars.UPPER_HALF_BLOCK


@pytest.mark.parametrize(*fast_and_slow_render_mark)
@rendering_test
def test_square_fullcolor_sets_pixel_lower():

    sc = TM.Screen(size=(3, 3))
    sc.data.square.set_at((0,1))
    sc.update((0, 0))
    yield None
    assert sc.data.square.get_at((0,1)) is TM.DEFAULT_FG
    assert sc.data.square.get_at((0,0)) is TM.DEFAULT_BG
    assert sc.data[0,0].value == TM.subpixels.HalfChars.LOWER_HALF_BLOCK


@pytest.mark.parametrize(*fast_and_slow_render_mark)
@rendering_test
def test_square_fullcolor_sets_both_pixels_yelds_full_block():

    sc = TM.Screen(size=(3, 3))
    sc.data.square.set_at((0,0))
    sc.data.square.set_at((0,1))
    sc.update((0, 0))
    yield None
    assert sc.data.square.get_at((0,1)) is TM.DEFAULT_FG
    assert sc.data.square.get_at((0,0)) is TM.DEFAULT_FG
    assert sc.data[0,0].value == TM.subpixels.HalfChars.FULL_BLOCK


@pytest.mark.parametrize(*fast_and_slow_render_mark)
@rendering_test
def test_square_fullcolor_set_half_pixel_to_other_color_than_default_preserves_other_half():

    color = TM.Color("blue")

    sc = TM.Screen(size=(3, 3))
    sc.data.square.set_at((0,0))
    sc.data.context.color = color
    sc.data.square.set_at((0,1))
    sc.update((0, 0))
    yield None
    assert sc.data.square.get_at((0,0)) is TM.DEFAULT_FG
    assert sc.data.square.get_at((0,1)) == color
    assert sc.data[0,0].background == color
    assert sc.data[0,0].value == TM.subpixels.HalfChars.UPPER_HALF_BLOCK


@pytest.mark.parametrize(*fast_and_slow_render_mark)
@rendering_test
def test_square_fullcolor_set_half_pixel_to_different_color_preserves_other_half():

    color = TM.Color("blue")
    color2 = TM.Color("red")

    sc = TM.Screen(size=(3, 3))
    sc.data.context.color = color
    sc.data.square.set_at((0,0))
    sc.data.context.color = color2
    sc.data.square.set_at((0,1))
    sc.update((0, 0))
    yield None
    assert sc.data.square.get_at((0,0)) == color
    assert sc.data.square.get_at((0,1)) == color2
    assert sc.data[0,0].background == color
    assert sc.data[0,0].foreground == color2
    assert sc.data[0,0].value == TM.subpixels.HalfChars.LOWER_HALF_BLOCK


@pytest.mark.parametrize(*fast_and_slow_render_mark)
@rendering_test
def test_square_fullcolor_resets_pixel():

    sc = TM.Screen(size=(3, 3))
    sc[0,0] = TM.values.FULL_BLOCK
    sc.data.square.reset_at((0,0))
    sc.update((0, 0))
    yield None
    assert sc.data.square.get_at((0,0)) is TM.DEFAULT_BG
    assert sc.data.square.get_at((0,1)) is TM.DEFAULT_FG
    assert sc.data[0,0].value == TM.subpixels.HalfChars.LOWER_HALF_BLOCK

@pytest.mark.parametrize(*fast_and_slow_render_mark)
@rendering_test
def test_square_fullcolor_resets_pixel_lower():

    sc = TM.Screen(size=(3, 3))
    sc[0,0] = TM.values.FULL_BLOCK
    sc.data.square.reset_at((0,1))
    sc.update((0, 0))
    yield None
    assert sc.data.square.get_at((0,0)) is TM.DEFAULT_FG
    assert sc.data.square.get_at((0,1)) is TM.DEFAULT_BG
    assert sc.data[0,0].value == TM.subpixels.HalfChars.UPPER_HALF_BLOCK


@pytest.mark.parametrize(*fast_and_slow_render_mark)
@rendering_test
def test_square_fullcolor_resets_both_pixels_yelds_full_block():

    sc = TM.Screen(size=(3, 3))
    sc[0,0] = TM.values.FULL_BLOCK
    sc.data.square.reset_at((0,0))
    sc.data.square.reset_at((0,1))
    sc.update((0, 0))
    yield None
    assert sc.data.square.get_at((0,1)) is TM.DEFAULT_BG
    assert sc.data.square.get_at((0,0)) is TM.DEFAULT_BG
    assert sc.data[0,0].value == TM.subpixels.HalfChars.EMPTY


@pytest.mark.parametrize(*fast_and_slow_render_mark)
@rendering_test
def test_square_fullcolor_reset_half_pixel_to_other_color_than_default_preserves_other_half():

    color = TM.Color("blue")

    sc = TM.Screen(size=(3, 3))
    sc[0,0] = TM.values.FULL_BLOCK
    sc.data.square.reset_at((0,0))
    sc.data.context.background = color
    sc.data.square.reset_at((0,1))
    sc.update((0, 0))
    yield None
    assert sc.data.square.get_at((0,0)) is TM.DEFAULT_BG
    assert sc.data.square.get_at((0,1)) == color
    assert sc.data[0,0].background == TM.DEFAULT_BG
    assert sc.data[0,0].value == TM.subpixels.HalfChars.LOWER_HALF_BLOCK


@pytest.mark.parametrize(*fast_and_slow_render_mark)
@rendering_test
def test_square_fullcolor_reset_half_pixel_to_different_color_preserves_other_half():

    color = TM.Color("blue")
    color2 = TM.Color("red")

    sc = TM.Screen(size=(3, 3))
    sc[0,0] = TM.values.FULL_BLOCK
    sc.data.context.background = color
    sc.data.square.reset_at((0,0))

    assert sc.data[0,0].value == TM.subpixels.HalfChars.LOWER_HALF_BLOCK
    assert sc.data[0,0].background == color

    sc.data.context.background = color2
    sc.data.square.reset_at((0,1))
    sc.update((0, 0))
    yield None
    assert sc.data.square.get_at((0,0)) == color
    assert sc.data.square.get_at((0,1)) == color2
    assert sc.data[0,0].foreground == color
    assert sc.data[0,0].background == color2
    assert sc.data[0,0].value == TM.subpixels.HalfChars.UPPER_HALF_BLOCK
