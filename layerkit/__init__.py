"""layerkit: a small library for building layer-based image compositions.

    from layerkit import Document

    doc = Document(800, 600)
    doc.add_image_layer("background.png", name="Background")
    top = doc.add_image_layer("logo.png", name="Logo", opacity=0.8, blend_mode="multiply")
    top.crop((0, 0, 200, 200)).adjust_brightness(1.1)
    doc.export("out.png")
"""

from .blend import BLEND_MODES, composite_over
from .card import (
    extract_dark_bg_color,
    generate_card,
    generate_cards_batch,
    generate_cards_from_dir,
    parse_mapping_file,
    remove_watermark,
)
from .document import Document
from .layer import VALID_BLEND_MODES, Layer

__all__ = [
    "Document",
    "Layer",
    "VALID_BLEND_MODES",
    "BLEND_MODES",
    "composite_over",
    "generate_card",
    "generate_cards_batch",
    "generate_cards_from_dir",
    "parse_mapping_file",
    "extract_dark_bg_color",
    "remove_watermark",
]

__version__ = "0.1.0"
