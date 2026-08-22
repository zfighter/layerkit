import numpy as np
import pytest

from layerkit.blend import composite_over


def test_normal_full_opacity_replaces_backdrop():
    backdrop = np.zeros((2, 2, 4))
    backdrop[..., :3] = 0.2  # dark gray, arbitrary
    backdrop[..., 3] = 1.0  # opaque

    source_rgb = np.full((2, 2, 3), 0.9)
    source_alpha = np.ones((2, 2, 1))

    out = composite_over(backdrop, source_rgb, source_alpha, "normal")
    assert np.allclose(out[..., :3], 0.9)
    assert np.allclose(out[..., 3], 1.0)


def test_zero_alpha_source_leaves_backdrop_unchanged():
    backdrop = np.zeros((2, 2, 4))
    backdrop[..., :3] = 0.4
    backdrop[..., 3] = 1.0

    source_rgb = np.full((2, 2, 3), 0.9)
    source_alpha = np.zeros((2, 2, 1))

    out = composite_over(backdrop, source_rgb, source_alpha, "normal")
    assert np.allclose(out, backdrop)


def test_multiply_darkens():
    backdrop = np.zeros((1, 1, 4))
    backdrop[..., :3] = 0.5
    backdrop[..., 3] = 1.0

    source_rgb = np.full((1, 1, 3), 0.5)
    source_alpha = np.ones((1, 1, 1))

    out = composite_over(backdrop, source_rgb, source_alpha, "multiply")
    assert np.allclose(out[..., :3], 0.25)


def test_transparent_backdrop_alpha_accumulates():
    backdrop = np.zeros((1, 1, 4))  # fully transparent

    source_rgb = np.full((1, 1, 3), 0.6)
    source_alpha = np.full((1, 1, 1), 0.5)

    out = composite_over(backdrop, source_rgb, source_alpha, "normal")
    assert np.isclose(out[0, 0, 3], 0.5)
    assert np.allclose(out[0, 0, :3], 0.6)


def test_unknown_mode_raises():
    backdrop = np.zeros((1, 1, 4))
    source_rgb = np.zeros((1, 1, 3))
    source_alpha = np.ones((1, 1, 1))
    with pytest.raises(ValueError):
        composite_over(backdrop, source_rgb, source_alpha, "not_a_mode")
