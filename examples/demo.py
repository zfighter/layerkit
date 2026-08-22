"""Build a small layered composition end-to-end and export it.

Generates all its own source imagery (a gradient, a shape, a brush stroke)
so it runs standalone with no input files needed.

Run with:

    python examples/demo.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PIL import Image, ImageDraw

from layerkit import Document, Layer


def make_gradient(size, color_a, color_b) -> Image.Image:
    w, h = size
    img = Image.new("RGB", size)
    pixels = img.load()
    for y in range(h):
        t = y / max(h - 1, 1)
        row = tuple(int(a + (b - a) * t) for a, b in zip(color_a, color_b))
        for x in range(w):
            pixels[x, y] = row
    return img.convert("RGBA")


def main() -> None:
    doc = Document(600, 400, background=(255, 255, 255, 255))

    # Bottom layer: a gradient background.
    bg = doc.new_layer("Gradient")
    bg.image = make_gradient((600, 400), (30, 30, 60), (255, 140, 90))

    # Middle layer: a translucent circle, screen-blended and offset.
    shape_img = Image.new("RGBA", (300, 300), (0, 0, 0, 0))
    ImageDraw.Draw(shape_img).ellipse((20, 20, 280, 280), fill=(0, 200, 255, 220))
    circle = doc.add_layer(
        Layer(shape_img, name="Circle", x=150, y=50, opacity=0.85, blend_mode="screen")
    )
    # Edit that layer in place: crop a bit off the edge, then brighten it.
    circle.crop((10, 10, 290, 290)).adjust_brightness(1.15)

    # Top layer: a freehand brush stroke.
    stroke_layer = doc.new_layer("Brush Stroke")
    stroke_layer.draw_brush_stroke(
        [(80, 350), (200, 300), (320, 340), (450, 280)],
        color=(255, 255, 255, 230),
        width=10,
    )

    out_path = os.path.join(os.path.dirname(__file__), "demo_output.png")
    doc.export(out_path)

    print(f"Wrote {out_path}")
    print(doc)
    for i, layer in enumerate(doc.layers):
        print(f"  [{i}] {layer!r}")

    # Try hiding a layer and re-exporting, to show layer visibility toggling.
    doc.set_visible("Circle", False)
    hidden_path = os.path.join(os.path.dirname(__file__), "demo_output_no_circle.png")
    doc.export(hidden_path)
    print(f"Wrote {hidden_path} (Circle layer hidden)")


if __name__ == "__main__":
    main()
