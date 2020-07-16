import random
from collections.abc import Sequence
import terminedia as TM
from terminedia.text.style import StyledSequence, SpecialMark, Mark, MLTokenizer
from terminedia.values import CONTINUATION, EMPTY, TRANSPARENT

import pytest

from conftest import rendering_test, fast_render_mark

# @pytest.mark.fixture
def styled_text():
    sc = TM.Screen((20, 10))
    sh = TM.shape((20, 10))
    sp1 = sc.data.sprites.add(sh)
    text_plane = sh.text[1]
    return sc, sh, text_plane

SMILEY = "\U0001F642"

@pytest.mark.parametrize(*fast_render_mark)
@rendering_test
def test_double_width_char_in_shape_uses_2_cells():
    sc, sh, text_plane = styled_text()
    sh[5,5] = SMILEY
    sc.update()
    yield None
    assert sh[5,5].value == SMILEY
    assert sh[6, 5].value == CONTINUATION
    assert sh[7, 5].value == TRANSPARENT


@pytest.mark.parametrize(*fast_render_mark)
@rendering_test
def test_double_width_char_in_text_1_uses_2_cells():
    sc, sh, text_plane = styled_text()
    sh.text[1][5,5] = SMILEY + "*"
    sc.update()
    yield None
    assert sh[5,5].value == SMILEY
    assert sh[6, 5].value == CONTINUATION
    assert sh[7, 5].value == "*"
    assert len(next(iter(sh.text[1].writtings)).text) == 2

