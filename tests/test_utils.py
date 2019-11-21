import pytest

from terminedia.utils import Spatial


def test_spatial_combine_translations():
    a = Spatial(translate=(1,0))
    b = Spatial(translate=(0, 1))
    c = a @ b
    assert c[0,2] == 1 and c[1, 2] == 1


def test_spatial_forward_translation_works():
    a = Spatial(translate=(1,1))
    assert (1, 1) * a == (2, 2)


def test_spatial_backward_translation_works():
    a = Spatial(translate=(1,1))
    assert (1, 1) / a == (0, 0)

