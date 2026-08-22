#!/usr/bin/env python3
"""CLI entry point for building a photo card. See layerkit/card.py for the API.

    python generate_card.py --image photo.jpg --cn "日落时分" --en "Sunset over the bay" --out card.png
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from layerkit.card import _main

if __name__ == "__main__":
    _main()
