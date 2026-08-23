"""Generate a 393x852 photo "card": a dark background auto-matched to the
photo's dominant color, a top image tile with rounded bottom corners, and a
Chinese + English text block below it -- three layers built on top of
:class:`~layerkit.document.Document`.

    from layerkit.card import generate_card

    generate_card(
        "photo.jpg",
        cn_text="日落时分",
        en_text="Sunset over the bay",
        out_path="card.png",
    )

Or from the command line::

    python -m layerkit.card --image photo.jpg --cn "日落时分" --en "Sunset over the bay" --out card.png
"""
from __future__ import annotations

import argparse
import colorsys
import os
from pathlib import Path
from typing import Iterable, List, Mapping, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

from .document import Document
from .layer import Layer

# -- card geometry, in logical (@1x) points ----------------------------------------
CARD_WIDTH = 393
CARD_HEIGHT = 852
IMAGE_WIDTH = 393
IMAGE_HEIGHT = 612
IMAGE_CORNER_RADIUS = 35  # only the image's bottom two corners are rounded

TEXT_MARGIN_X = 100  # required clearance on each side; text is centered and sized to fit within it
TEXT_LINE_GAP = 14  # gap between the EN title and the CN subtitle
EN_MAX_FONT_SIZE = 56  # large, bold, hand-lettered -- the card's primary line
CN_MAX_FONT_SIZE = 28  # smaller, plain -- secondary line below it
TEXT_MIN_FONT_SIZE = 10  # never shrink past this, even for very long text

EN_TEXT_COLOR = (255, 255, 255, 255)
CN_TEXT_COLOR = (255, 255, 255, 255)

# PingFang.ttc ships on macOS with several weights bundled as face indices.
FONT_CN_PATH = "/System/Library/Fonts/PingFang.ttc"
FONT_CN_INDEX = 5  # PingFang SC Medium

# Noteworthy is a rounded, hand-lettered display face -- used for the large
# English title so it reads as a playful headline rather than plain body text.
FONT_EN_PATH = "/System/Library/Fonts/Noteworthy.ttc"
FONT_EN_INDEX = 1  # Noteworthy Bold

# (left, top, right, bottom) as fractions of image width/height -- covers the
# bottom-right corner where AI generators commonly stamp a watermark (e.g.
# Doubao's "豆包AI生成"). Validated against several 豆包-generated sources.
WATERMARK_REGION = (0.75, 0.92, 1.0, 1.0)
WATERMARK_INPAINT_RADIUS = 5


def remove_watermark(
    image: Image.Image,
    region: Tuple[float, float, float, float] = WATERMARK_REGION,
    inpaint_radius: int = WATERMARK_INPAINT_RADIUS,
) -> Image.Image:
    """Erase a corner watermark by inpainting it from the surrounding pixels.

    ``region`` is a ``(left, top, right, bottom)`` box given as *fractions*
    of the image's width/height; the default targets the bottom-right corner
    where AI image generators commonly stamp a watermark (e.g. Doubao's
    "豆包AI生成"). Uses OpenCV's fast-marching inpaint (Telea's algorithm),
    which reconstructs the region from its boundary inward.

    This works best when run against the original, full-resolution source
    photo (before any cover-crop/resize) -- more real pixels around the
    watermark means a better reconstruction. On a plain or gently textured
    background it blends in almost perfectly; on a background with fine
    detail running right up into the corner (e.g. grass blades, patterned
    fabric), the patch will come out visibly softer than its surroundings --
    inpainting can't invent detail that was never captured.
    """
    rgb = np.array(image.convert("RGB"))
    h, w = rgb.shape[:2]
    left, top, right, bottom = region
    x0, y0 = int(w * left), int(h * top)
    x1, y1 = int(w * right), int(h * bottom)

    mask = np.zeros((h, w), dtype=np.uint8)
    mask[y0:y1, x0:x1] = 255

    inpainted = cv2.inpaint(rgb, mask, inpaint_radius, cv2.INPAINT_TELEA)
    result = Image.fromarray(inpainted)

    if image.mode == "RGBA":
        result = result.convert("RGBA")
        result.putalpha(image.getchannel("A"))
    return result


def extract_dark_bg_color(
    image: Image.Image,
    target_value: float = 0.28,
    min_saturation: float = 0.35,
    sample_size: int = 120,
) -> Tuple[int, int, int]:
    """Pick a dark, saturated background color that matches the photo's dominant hue.

    Downsamples the image, quantizes it to a small palette, and takes the most
    common color with reasonable saturation (falling back to the single most
    common color overall if none are saturated enough). That color's hue and
    saturation are kept but its brightness is pushed down to ``target_value``,
    the same trick Apple Music / Spotify use to derive a dark accent color
    from artwork.
    """
    thumb = image.convert("RGB").resize((sample_size, sample_size))
    quantized = thumb.quantize(colors=8, method=Image.MEDIANCUT)
    palette = quantized.getpalette()[: 8 * 3]
    counts = sorted(quantized.getcolors(), reverse=True)

    candidates = []
    for count, idx in counts:
        r, g, b = palette[idx * 3 : idx * 3 + 3]
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        candidates.append((count, h, s, v))

    saturated = [c for c in candidates if c[2] >= min_saturation]
    pool = saturated if saturated else candidates
    _, h, s, _ = pool[0]

    s = min(1.0, max(s, 0.45))
    r, g, b = colorsys.hsv_to_rgb(h, s, target_value)
    return (round(r * 255), round(g * 255), round(b * 255))


def _cover_resize(image: Image.Image, target_size: Tuple[int, int]) -> Image.Image:
    """Resize+crop like CSS `object-fit: cover`: fills target_size, cropping overflow."""
    return ImageOps.fit(image, target_size, method=Image.LANCZOS, centering=(0.5, 0.5))


def _round_bottom_corners(image: Image.Image, radius: int) -> Image.Image:
    """Return a copy of ``image`` with only its bottom-left/bottom-right corners rounded."""
    image = image.convert("RGBA")
    mask = Image.new("L", image.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle(
        [0, 0, image.width - 1, image.height - 1],
        radius=radius,
        fill=255,
        corners=(False, False, True, True),  # top-left, top-right, bottom-left, bottom-right
    )
    image.putalpha(mask)
    return image


def _fit_font(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_path: str,
    font_index: int,
    max_width: float,
    max_size: int,
    min_size: int = TEXT_MIN_FONT_SIZE,
) -> Tuple[ImageFont.FreeTypeFont, Tuple[int, int, int, int]]:
    """Find the largest font size (<= max_size) whose rendered width fits max_width.

    Shrinks one point at a time from ``max_size`` down to ``min_size``. Returns
    the chosen font plus its ``textbbox`` at the origin, so callers don't have
    to re-measure it.
    """
    size = max_size
    while size > min_size:
        font = ImageFont.truetype(font_path, size, index=font_index)
        bbox = draw.textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= max_width:
            return font, bbox
        size -= 1
    font = ImageFont.truetype(font_path, min_size, index=font_index)
    return font, draw.textbbox((0, 0), text, font=font)


def generate_card(
    image_path: str,
    cn_text: str = "",
    en_text: str = "",
    out_path: str = "card.png",
    scale: int = 3,
    bg_color: Optional[Tuple[int, int, int]] = None,
    remove_watermark_flag: bool = True,
    watermark_region: Tuple[float, float, float, float] = WATERMARK_REGION,
) -> Tuple[str, Tuple[int, int, int]]:
    """Compose the 3-layer card (background / image / text) and export it.

    Args:
        image_path: source photo used for the top image tile.
        cn_text: Chinese title line, drawn bold and larger.
        en_text: English subtitle line, drawn regular and smaller, below the title.
        out_path: where to save the composed PNG.
        scale: render multiplier for high-resolution export. The card's
            logical size is 393x852 (an iPhone point size); the default
            ``scale=3`` exports at 1179x2556, a typical @3x resolution.
        bg_color: force a specific RGB background color instead of
            auto-detecting one from the photo.
        remove_watermark_flag: if True (the default), inpaint over a corner
            watermark (see :func:`remove_watermark`) before doing anything
            else with the photo -- so the background-color extraction, crop,
            and rounding all operate on the cleaned-up image.
        watermark_region: forwarded to :func:`remove_watermark`; override if
            a particular source's watermark sits somewhere else.

    Returns:
        ``(out_path, bg_color_used)``.
    """
    src = Image.open(image_path)
    src.load()

    if remove_watermark_flag:
        src = remove_watermark(src, region=watermark_region)

    resolved_bg = bg_color or extract_dark_bg_color(src)
    canvas_size = (CARD_WIDTH * scale, CARD_HEIGHT * scale)

    doc = Document(*canvas_size, background=(*resolved_bg, 255))

    # Layer 1: solid background color, matched to the photo.
    doc.add_layer(Layer(Image.new("RGBA", canvas_size, (*resolved_bg, 255)), name="Background"))

    # Layer 2: the photo, cover-cropped to 393x612 and rounded on the bottom edge only.
    fitted = _cover_resize(src, (IMAGE_WIDTH * scale, IMAGE_HEIGHT * scale))
    rounded = _round_bottom_corners(fitted, IMAGE_CORNER_RADIUS * scale)
    doc.add_layer(Layer(rounded, name="Image", x=0, y=0))

    # Layer 3: EN title (large, bold, hand-lettered) + CN subtitle (smaller,
    # plain), stacked and centered as a block in the solid-color zone below
    # the image.
    text_layer = Layer.blank(canvas_size, name="Text")
    draw = ImageDraw.Draw(text_layer.image)

    max_text_width = canvas_size[0] - 2 * TEXT_MARGIN_X * scale

    lines = []
    if en_text:
        lines.append((en_text, FONT_EN_PATH, FONT_EN_INDEX, EN_MAX_FONT_SIZE, EN_TEXT_COLOR))
    if cn_text:
        lines.append((cn_text, FONT_CN_PATH, FONT_CN_INDEX, CN_MAX_FONT_SIZE, CN_TEXT_COLOR))

    line_gap = TEXT_LINE_GAP * scale
    measured = []
    block_height = 0.0
    for text, font_path, font_index, max_size, color in lines:
        font, bbox = _fit_font(draw, text, font_path, font_index, max_text_width, max_size * scale)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        measured.append((text, font, color, w, h, bbox))
        block_height += h
    block_height += line_gap * max(len(lines) - 1, 0)

    zone_top = IMAGE_HEIGHT * scale
    zone_height = canvas_size[1] - zone_top
    y = zone_top + (zone_height - block_height) / 2

    for text, font, color, w, h, bbox in measured:
        x = (canvas_size[0] - w) / 2 - bbox[0]
        draw.text((x, y - bbox[1]), text, font=font, fill=color)
        y += h + line_gap
    doc.add_layer(text_layer)

    doc.export(out_path)
    return out_path, resolved_bg


def generate_cards_batch(
    items: Iterable[Mapping[str, object]],
    out_dir: str = "cards",
    scale: int = 3,
    remove_watermark_flag: bool = True,
) -> List[Tuple[str, Tuple[int, int, int]]]:
    """Run :func:`generate_card` over a batch of images, one call each.

    Args:
        items: an iterable of dicts, one per image, with keys:
            - ``image`` (required): path to the source photo.
            - ``cn`` (optional): Chinese title text, defaults to ``""``.
            - ``en`` (optional): English subtitle text, defaults to ``""``.
            - ``out_name`` (optional): output filename stem; defaults to the
              source image's own filename stem (e.g. ``photo1.jpg`` -> ``photo1.png``).
            - ``bg_color`` (optional): force a specific ``(r, g, b)`` background
              instead of auto-detecting one for that image.
            - ``remove_watermark`` (optional): per-item override of
              ``remove_watermark_flag``.
        out_dir: directory the output PNGs are written into (created if needed).
        scale: render multiplier, forwarded to every :func:`generate_card` call.
        remove_watermark_flag: default corner-watermark removal for every
            item (see :func:`remove_watermark`); override per item with the
            ``remove_watermark`` key.

    Returns:
        A list of ``(out_path, bg_color_used)``, in the same order as ``items``.
    """
    os.makedirs(out_dir, exist_ok=True)
    results = []
    for item in items:
        image_path = str(item["image"])
        stem = str(item["out_name"]) if item.get("out_name") else Path(image_path).stem
        out_path = os.path.join(out_dir, f"{stem}.png")
        result = generate_card(
            image_path,
            cn_text=str(item.get("cn", "")),
            en_text=str(item.get("en", "")),
            out_path=out_path,
            scale=scale,
            bg_color=item.get("bg_color"),  # type: ignore[arg-type]
            remove_watermark_flag=bool(item.get("remove_watermark", remove_watermark_flag)),
        )
        results.append(result)
    return results


def parse_mapping_file(path: str) -> List[dict]:
    """Parse a ``filename | cn text | en text`` mapping file.

    One image per line::

        # lines starting with '#' and blank lines are ignored
        photo1.jpg | 身高 | Height
        photo2.jpg | 音乐家 | Musicians
        photo3.jpg | 只有中文

    - The filename must match a file in the images directory exactly
      (including extension); it's looked up relative to that directory later.
    - The EN field is optional -- a line with just ``filename | cn text`` is
      fine and leaves the English line blank on the card.
    - Fields are split on ``|`` and whitespace-trimmed. The full-width
      ``｜`` (U+FF5C) that Chinese IMEs often substitute for ``|`` is
      normalized to ``|`` first, so either one works as the delimiter.

    Returns a list of ``{"image": ..., "cn": ..., "en": ...}`` dicts, in file
    order, where ``image`` is still the bare filename as written (not yet
    resolved to a full path).
    """
    items = []
    with open(path, "r", encoding="utf-8") as f:
        for lineno, raw_line in enumerate(f, start=1):
            line = raw_line.strip().replace("｜", "|")  # fullwidth "｜" -> ASCII "|"
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 2 or not parts[0]:
                raise ValueError(
                    f"{path}:{lineno}: expected 'filename | cn text | en text', got: {raw_line!r}"
                )
            items.append(
                {
                    "image": parts[0],
                    "cn": parts[1] if len(parts) > 1 else "",
                    "en": parts[2] if len(parts) > 2 else "",
                }
            )
    return items


def generate_cards_from_dir(
    images_dir: str,
    mapping_path: Optional[str] = None,
    out_dir: str = "cards",
    scale: int = 3,
    remove_watermark_flag: bool = True,
) -> List[Tuple[str, Tuple[int, int, int]]]:
    """Batch-generate cards for every row of a mapping file in ``images_dir``.

    Args:
        images_dir: directory holding the source photos.
        mapping_path: path to the mapping ``.txt`` file (see
            :func:`parse_mapping_file` for its format). Defaults to
            ``<images_dir>/mapping.txt``.
        out_dir: directory the output PNGs are written into (created if needed).
        scale: render multiplier, forwarded to every card.
        remove_watermark_flag: forwarded to :func:`generate_cards_batch` --
            inpaint over a corner watermark (see :func:`remove_watermark`)
            before processing each photo. Default on.

    Rows whose image file can't be found are skipped with a printed warning
    instead of aborting the whole batch.

    Returns:
        A list of ``(out_path, bg_color_used)``, one per successfully
        generated card, in mapping-file order.
    """
    mapping_path = mapping_path or os.path.join(images_dir, "mapping.txt")
    rows = parse_mapping_file(mapping_path)

    items = []
    for row in rows:
        image_path = os.path.join(images_dir, row["image"])
        if not os.path.isfile(image_path):
            print(f"[skip] image not found: {image_path}")
            continue
        items.append(
            {
                "image": image_path,
                "cn": row["cn"],
                "en": row["en"],
                "out_name": Path(row["image"]).stem,
            }
        )

    return generate_cards_batch(items, out_dir=out_dir, scale=scale, remove_watermark_flag=remove_watermark_flag)


def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a 393x852 photo card with a background color auto-matched to the photo."
    )
    parser.add_argument("--image", required=True, help="Path to the source photo")
    parser.add_argument("--cn", default="", help="Chinese title text")
    parser.add_argument("--en", default="", help="English subtitle text")
    parser.add_argument("--out", default="card.png", help="Output PNG path")
    parser.add_argument("--scale", type=int, default=3, help="Render scale multiplier (default 3 -> 1179x2556)")
    parser.add_argument(
        "--no-remove-watermark",
        action="store_true",
        help="Skip corner-watermark inpainting (it's applied by default)",
    )
    args = parser.parse_args()

    out_path, bg = generate_card(
        args.image,
        args.cn,
        args.en,
        args.out,
        scale=args.scale,
        remove_watermark_flag=not args.no_remove_watermark,
    )
    print(f"Wrote {out_path} ({CARD_WIDTH * args.scale}x{CARD_HEIGHT * args.scale}), background={bg}")


if __name__ == "__main__":
    _main()
