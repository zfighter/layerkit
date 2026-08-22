"""Blend-mode math used when compositing layers together.

All functions operate on ``float64`` numpy arrays scaled to ``[0, 1]``, and
follow the standard Porter-Duff "source-over" operator combined with a CSS/
Photoshop-style blend function, per the W3C compositing spec formula:

    Co = (1 - as) * Cb + as * ((1 - ab) * Cs + ab * B(Cb, Cs))

where ``Cb``/``ab`` are the backdrop color/alpha and ``Cs``/``as`` are the
source color/alpha (the layer's own alpha channel multiplied by its opacity).
"""
from __future__ import annotations

from typing import Callable, Dict

import numpy as np

BlendFn = Callable[[np.ndarray, np.ndarray], np.ndarray]


def _normal(cb: np.ndarray, cs: np.ndarray) -> np.ndarray:
    return cs


def _multiply(cb: np.ndarray, cs: np.ndarray) -> np.ndarray:
    return cb * cs


def _screen(cb: np.ndarray, cs: np.ndarray) -> np.ndarray:
    return cb + cs - cb * cs


def _darken(cb: np.ndarray, cs: np.ndarray) -> np.ndarray:
    return np.minimum(cb, cs)


def _lighten(cb: np.ndarray, cs: np.ndarray) -> np.ndarray:
    return np.maximum(cb, cs)


def _difference(cb: np.ndarray, cs: np.ndarray) -> np.ndarray:
    return np.abs(cb - cs)


def _add(cb: np.ndarray, cs: np.ndarray) -> np.ndarray:
    return np.clip(cb + cs, 0.0, 1.0)


def _subtract(cb: np.ndarray, cs: np.ndarray) -> np.ndarray:
    return np.clip(cb - cs, 0.0, 1.0)


def _overlay(cb: np.ndarray, cs: np.ndarray) -> np.ndarray:
    return np.where(cb <= 0.5, 2 * cb * cs, 1 - 2 * (1 - cb) * (1 - cs))


def _hard_light(cb: np.ndarray, cs: np.ndarray) -> np.ndarray:
    # Hard light is overlay with the two inputs swapped.
    return _overlay(cs, cb)


def _soft_light(cb: np.ndarray, cs: np.ndarray) -> np.ndarray:
    d = np.where(
        cb <= 0.25,
        ((16 * cb - 12) * cb + 4) * cb,
        np.sqrt(np.clip(cb, 0.0, 1.0)),
    )
    return np.where(
        cs <= 0.5,
        cb - (1 - 2 * cs) * cb * (1 - cb),
        cb + (2 * cs - 1) * (d - cb),
    )


BLEND_MODES: Dict[str, BlendFn] = {
    "normal": _normal,
    "multiply": _multiply,
    "screen": _screen,
    "darken": _darken,
    "lighten": _lighten,
    "difference": _difference,
    "add": _add,
    "subtract": _subtract,
    "overlay": _overlay,
    "hard_light": _hard_light,
    "soft_light": _soft_light,
}


def composite_over(
    backdrop: np.ndarray,
    source_rgb: np.ndarray,
    source_alpha: np.ndarray,
    mode: str = "normal",
) -> np.ndarray:
    """Composite ``source`` over ``backdrop`` using Porter-Duff "over" + a blend mode.

    Args:
        backdrop: ``(H, W, 4)`` straight-alpha RGBA float array in ``[0, 1]``.
        source_rgb: ``(H, W, 3)`` float array in ``[0, 1]``.
        source_alpha: ``(H, W, 1)`` float array in ``[0, 1]`` -- the layer's
            alpha channel already multiplied by its opacity.
        mode: one of the keys in :data:`BLEND_MODES`.

    Returns:
        ``(H, W, 4)`` straight-alpha RGBA float array in ``[0, 1]``.
    """
    if mode not in BLEND_MODES:
        raise ValueError(f"Unknown blend mode: {mode!r}. Available: {sorted(BLEND_MODES)}")
    blend_fn = BLEND_MODES[mode]

    cb = backdrop[..., :3]
    ab = backdrop[..., 3:4]

    blended = blend_fn(cb, source_rgb)
    mixed = (1 - ab) * source_rgb + ab * blended

    ao = source_alpha + ab * (1 - source_alpha)
    safe_ao = np.where(ao > 1e-6, ao, 1.0)
    co = (mixed * source_alpha + cb * ab * (1 - source_alpha)) / safe_ao
    co = np.where(ao > 1e-6, co, 0.0)

    out = np.concatenate([co, ao], axis=-1)
    return np.clip(out, 0.0, 1.0)
