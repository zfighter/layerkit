"""A single editable image layer."""
from __future__ import annotations

from typing import Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

VALID_BLEND_MODES = (
    "normal",
    "multiply",
    "screen",
    "darken",
    "lighten",
    "difference",
    "add",
    "subtract",
    "overlay",
    "hard_light",
    "soft_light",
)


class Layer:
    """One image layer inside a :class:`~layerkit.document.Document`.

    A layer owns its own RGBA image plus an ``(x, y)`` offset describing
    where its top-left corner sits on the parent canvas. Layers can be
    smaller or larger than the canvas -- content outside canvas bounds is
    simply clipped at composite time.
    """

    def __init__(
        self,
        image: Image.Image,
        name: str = "Layer",
        *,
        x: int = 0,
        y: int = 0,
        opacity: float = 1.0,
        blend_mode: str = "normal",
        visible: bool = True,
    ) -> None:
        self.name = name
        self.image = image.convert("RGBA")
        self.x = x
        self.y = y
        self.opacity = opacity
        self.blend_mode = blend_mode
        self.visible = visible

    # -- construction helpers -------------------------------------------------
    @classmethod
    def from_file(cls, path: str, name: Optional[str] = None, **kwargs) -> "Layer":
        img = Image.open(path)
        img.load()
        return cls(img, name=name or path.rsplit("/", 1)[-1], **kwargs)

    @classmethod
    def blank(
        cls,
        size: Tuple[int, int],
        color: Tuple[int, int, int, int] = (0, 0, 0, 0),
        name: str = "Layer",
        **kwargs,
    ) -> "Layer":
        return cls(Image.new("RGBA", size, color), name=name, **kwargs)

    def duplicate(self, name: Optional[str] = None) -> "Layer":
        return Layer(
            self.image.copy(),
            name=name or f"{self.name} copy",
            x=self.x,
            y=self.y,
            opacity=self.opacity,
            blend_mode=self.blend_mode,
            visible=self.visible,
        )

    # -- properties -------------------------------------------------------------
    @property
    def opacity(self) -> float:
        return self._opacity

    @opacity.setter
    def opacity(self, value: float) -> None:
        if not 0.0 <= value <= 1.0:
            raise ValueError("opacity must be between 0.0 and 1.0")
        self._opacity = float(value)

    @property
    def blend_mode(self) -> str:
        return self._blend_mode

    @blend_mode.setter
    def blend_mode(self, value: str) -> None:
        if value not in VALID_BLEND_MODES:
            raise ValueError(f"Unknown blend mode {value!r}. Choose from {VALID_BLEND_MODES}")
        self._blend_mode = value

    @property
    def size(self) -> Tuple[int, int]:
        return self.image.size

    @property
    def bbox(self) -> Tuple[int, int, int, int]:
        w, h = self.size
        return (self.x, self.y, self.x + w, self.y + h)

    # -- geometry -----------------------------------------------------------------
    def move(self, dx: int, dy: int) -> "Layer":
        self.x += dx
        self.y += dy
        return self

    def move_to(self, x: int, y: int) -> "Layer":
        self.x, self.y = x, y
        return self

    def crop(self, box: Tuple[int, int, int, int]) -> "Layer":
        """Crop the layer's own image. ``box`` is in layer-local coordinates
        (left, top, right, bottom), matching ``PIL.Image.crop``."""
        left, top, _, _ = box
        self.image = self.image.crop(box)
        self.x += left
        self.y += top
        return self

    def resize(self, size: Tuple[int, int], resample: int = Image.LANCZOS) -> "Layer":
        self.image = self.image.resize(size, resample)
        return self

    def rotate(self, degrees: float, expand: bool = True) -> "Layer":
        self.image = self.image.rotate(degrees, expand=expand, resample=Image.BICUBIC)
        return self

    def flip_horizontal(self) -> "Layer":
        self.image = ImageOps.mirror(self.image)
        return self

    def flip_vertical(self) -> "Layer":
        self.image = ImageOps.flip(self.image)
        return self

    # -- pixel adjustments --------------------------------------------------------
    def adjust_brightness(self, factor: float) -> "Layer":
        self._replace_rgb(ImageEnhance.Brightness(self.image.convert("RGB")).enhance(factor))
        return self

    def adjust_contrast(self, factor: float) -> "Layer":
        self._replace_rgb(ImageEnhance.Contrast(self.image.convert("RGB")).enhance(factor))
        return self

    def adjust_saturation(self, factor: float) -> "Layer":
        self._replace_rgb(ImageEnhance.Color(self.image.convert("RGB")).enhance(factor))
        return self

    def grayscale(self) -> "Layer":
        gray = ImageOps.grayscale(self.image.convert("RGB")).convert("RGB")
        self._replace_rgb(gray)
        return self

    def invert(self) -> "Layer":
        self._replace_rgb(ImageOps.invert(self.image.convert("RGB")))
        return self

    def blur(self, radius: float = 2.0) -> "Layer":
        self.image = self.image.filter(ImageFilter.GaussianBlur(radius))
        return self

    def sharpen(self) -> "Layer":
        self._replace_rgb(self.image.convert("RGB").filter(ImageFilter.SHARPEN))
        return self

    def _replace_rgb(self, rgb_image: Image.Image) -> None:
        """Swap in a new RGB image while preserving the existing alpha channel."""
        alpha = self.image.getchannel("A")
        rgb_image = rgb_image.convert("RGB")
        rgb_image.putalpha(alpha)
        self.image = rgb_image

    # -- painting -----------------------------------------------------------------
    def draw_brush_stroke(
        self,
        points: Sequence[Tuple[float, float]],
        color: Tuple[int, int, int, int] = (0, 0, 0, 255),
        width: int = 4,
    ) -> "Layer":
        """Draw a freehand polyline stroke directly onto the layer (destructive).

        ``points`` are in layer-local coordinates, e.g. captured from mouse or
        stylus input. Round joints/caps are approximated with an ellipse at
        each vertex so the stroke doesn't look segmented.
        """
        if not points:
            return self
        draw = ImageDraw.Draw(self.image)
        r = width / 2
        if len(points) == 1:
            x, y = points[0]
            draw.ellipse((x - r, y - r, x + r, y + r), fill=color)
            return self
        draw.line(list(points), fill=color, width=width, joint="curve")
        for x, y in points:
            draw.ellipse((x - r, y - r, x + r, y + r), fill=color)
        return self

    def clear(self, color: Tuple[int, int, int, int] = (0, 0, 0, 0)) -> "Layer":
        self.image = Image.new("RGBA", self.size, color)
        return self

    def __repr__(self) -> str:
        return (
            f"Layer(name={self.name!r}, size={self.size}, pos=({self.x}, {self.y}), "
            f"opacity={self.opacity}, blend_mode={self.blend_mode!r}, visible={self.visible})"
        )
