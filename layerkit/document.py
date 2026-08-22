"""Document: an ordered stack of layers that can be composited to one image."""
from __future__ import annotations

from typing import List, Optional, Tuple, Union

import numpy as np
from PIL import Image

from .blend import composite_over
from .layer import Layer

LayerRef = Union[int, str, Layer]


class Document:
    """A canvas holding an ordered stack of :class:`~layerkit.layer.Layer`.

    Layers are stored bottom-to-top: ``layers[0]`` is the backmost layer and
    ``layers[-1]`` is the frontmost/topmost layer -- the same order they are
    painted in during compositing, and the order ``add_layer`` appends to by
    default.
    """

    def __init__(self, width: int, height: int, background: Tuple[int, int, int, int] = (0, 0, 0, 0)):
        self.width = width
        self.height = height
        self.background = background
        self.layers: List[Layer] = []

    # -- layer management ------------------------------------------------------------
    def add_layer(self, layer: Layer, index: Optional[int] = None) -> Layer:
        if index is None:
            self.layers.append(layer)
        else:
            self.layers.insert(index, layer)
        return layer

    def new_layer(self, name: str = "Layer", **kwargs) -> Layer:
        """Create a blank, canvas-sized, fully-transparent layer and add it."""
        layer = Layer.blank((self.width, self.height), name=name, **kwargs)
        return self.add_layer(layer)

    def add_image_layer(self, path: str, name: Optional[str] = None, **kwargs) -> Layer:
        layer = Layer.from_file(path, name=name, **kwargs)
        return self.add_layer(layer)

    def remove_layer(self, ref: LayerRef) -> Layer:
        layer = self.get_layer(ref)
        self.layers.remove(layer)
        return layer

    def get_layer(self, ref: LayerRef) -> Layer:
        if isinstance(ref, Layer):
            return ref
        if isinstance(ref, int):
            return self.layers[ref]
        for layer in self.layers:
            if layer.name == ref:
                return layer
        raise KeyError(f"No layer named {ref!r}")

    def rename_layer(self, ref: LayerRef, new_name: str) -> Layer:
        layer = self.get_layer(ref)
        layer.name = new_name
        return layer

    def set_visible(self, ref: LayerRef, visible: bool) -> Layer:
        layer = self.get_layer(ref)
        layer.visible = visible
        return layer

    def toggle_visible(self, ref: LayerRef) -> Layer:
        layer = self.get_layer(ref)
        layer.visible = not layer.visible
        return layer

    def move_layer(self, ref: LayerRef, new_index: int) -> None:
        """Reorder a layer to sit at ``new_index`` in the stack."""
        layer = self.get_layer(ref)
        self.layers.remove(layer)
        self.layers.insert(new_index, layer)

    def move_layer_up(self, ref: LayerRef) -> None:
        layer = self.get_layer(ref)
        idx = self.layers.index(layer)
        if idx < len(self.layers) - 1:
            self.layers[idx], self.layers[idx + 1] = self.layers[idx + 1], self.layers[idx]

    def move_layer_down(self, ref: LayerRef) -> None:
        layer = self.get_layer(ref)
        idx = self.layers.index(layer)
        if idx > 0:
            self.layers[idx], self.layers[idx - 1] = self.layers[idx - 1], self.layers[idx]

    # -- compositing --------------------------------------------------------------------
    def composite(self) -> Image.Image:
        """Flatten all visible layers, bottom to top, into a single RGBA image."""
        backdrop = np.zeros((self.height, self.width, 4), dtype=np.float64)
        if self.background:
            bg = np.array(self.background, dtype=np.float64) / 255.0
            if bg.shape[0] == 3:
                bg = np.append(bg, 1.0)
            backdrop[:, :, :] = bg

        for layer in self.layers:
            if not layer.visible or layer.opacity <= 0:
                continue

            placed = self._place_on_canvas(layer)
            src_rgb = placed[..., :3]
            src_alpha = placed[..., 3:4] * layer.opacity
            backdrop = composite_over(backdrop, src_rgb, src_alpha, layer.blend_mode)

        out = (np.clip(backdrop, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
        return Image.fromarray(out, mode="RGBA")

    def _place_on_canvas(self, layer: Layer) -> np.ndarray:
        """Paste a layer's image onto a canvas-sized float RGBA buffer, clipped to bounds."""
        canvas = np.zeros((self.height, self.width, 4), dtype=np.float64)
        arr = np.asarray(layer.image, dtype=np.float64) / 255.0
        lh, lw = arr.shape[:2]

        x0, y0 = layer.x, layer.y
        x1, y1 = x0 + lw, y0 + lh

        cx0, cy0 = max(x0, 0), max(y0, 0)
        cx1, cy1 = min(x1, self.width), min(y1, self.height)
        if cx0 >= cx1 or cy0 >= cy1:
            return canvas  # entirely off-canvas

        sx0, sy0 = cx0 - x0, cy0 - y0
        sx1, sy1 = sx0 + (cx1 - cx0), sy0 + (cy1 - cy0)

        canvas[cy0:cy1, cx0:cx1, :] = arr[sy0:sy1, sx0:sx1, :]
        return canvas

    def export(self, path: str, *, flatten_background: Optional[Tuple[int, int, int]] = None) -> None:
        """Composite the document and save it to ``path``.

        The output format is inferred from the file extension. Pass
        ``flatten_background`` (e.g. ``(255, 255, 255)``) to flatten onto an
        opaque background first -- required for formats without alpha, such
        as JPEG.
        """
        result = self.composite()
        if flatten_background is not None:
            base = Image.new("RGB", result.size, flatten_background)
            base.paste(result, mask=result.getchannel("A"))
            base.save(path)
        else:
            result.save(path)

    def __repr__(self) -> str:
        return f"Document({self.width}x{self.height}, {len(self.layers)} layers)"
