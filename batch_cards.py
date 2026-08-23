#!/usr/bin/env python3
"""Batch-generate cards for every image listed in a mapping file.

Reads ``origin_cards/mapping.txt`` by default -- one line per image,
formatted as ``图片文件名 | 中文文字 | 英文文字`` -- and writes one card per
row into ``cards/``, named after the source image.

    python batch_cards.py
    python batch_cards.py --dir origin_cards --mapping origin_cards/mapping.txt --out cards --scale 3

See :func:`layerkit.card.parse_mapping_file` for the mapping file format.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from layerkit.card import generate_cards_from_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch-generate photo cards from a directory + mapping.txt")
    parser.add_argument("--dir", default="origin_cards", help="Directory of source images (default: origin_cards)")
    parser.add_argument("--mapping", default=None, help="Mapping txt path (default: <dir>/mapping.txt)")
    parser.add_argument("--out", default="cards", help="Output directory for generated cards (default: cards)")
    parser.add_argument("--scale", type=int, default=3, help="Render scale multiplier (default: 3)")
    parser.add_argument(
        "--no-remove-watermark",
        action="store_true",
        help="Skip corner-watermark inpainting (it's applied by default)",
    )
    args = parser.parse_args()

    results = generate_cards_from_dir(
        args.dir,
        args.mapping,
        out_dir=args.out,
        scale=args.scale,
        remove_watermark_flag=not args.no_remove_watermark,
    )
    print(f"Generated {len(results)} card(s) into {args.out}/")
    for path, bg in results:
        print(f"  {path}  background={bg}")


if __name__ == "__main__":
    main()
