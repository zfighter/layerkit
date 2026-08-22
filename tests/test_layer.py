import pytest
from PIL import Image

from layerkit import Layer


def make_layer(size=(10, 10), color=(255, 0, 0, 255)):
    return Layer(Image.new("RGBA", size, color), name="L")


def test_opacity_validation():
    layer = make_layer()
    layer.opacity = 0.5
    assert layer.opacity == 0.5
    with pytest.raises(ValueError):
        layer.opacity = 1.5
    with pytest.raises(ValueError):
        layer.opacity = -0.1


def test_blend_mode_validation():
    layer = make_layer()
    layer.blend_mode = "multiply"
    assert layer.blend_mode == "multiply"
    with pytest.raises(ValueError):
        layer.blend_mode = "not_a_real_mode"


def test_crop_shrinks_image_and_shifts_offset():
    layer = make_layer((20, 20))
    layer.crop((5, 5, 15, 15))
    assert layer.size == (10, 10)
    assert (layer.x, layer.y) == (5, 5)


def test_resize_changes_size():
    layer = make_layer((10, 10))
    layer.resize((20, 40))
    assert layer.size == (20, 40)


def test_move_and_move_to():
    layer = make_layer()
    layer.move(3, 4)
    assert (layer.x, layer.y) == (3, 4)
    layer.move_to(100, 200)
    assert (layer.x, layer.y) == (100, 200)


def test_grayscale_preserves_alpha():
    layer = make_layer(color=(255, 0, 0, 128))
    layer.grayscale()
    r, g, b, a = layer.image.getpixel((0, 0))
    assert r == g == b  # gray
    assert a == 128  # alpha untouched


def test_draw_brush_stroke_paints_pixels():
    layer = make_layer((50, 50), color=(0, 0, 0, 0))
    layer.draw_brush_stroke([(5, 25), (45, 25)], color=(255, 255, 255, 255), width=6)
    assert layer.image.getpixel((25, 25))[3] > 0  # something was painted mid-stroke


def test_duplicate_is_independent_copy():
    layer = make_layer()
    dup = layer.duplicate()
    dup.opacity = 0.2
    dup.image.putpixel((0, 0), (0, 255, 0, 255))
    assert layer.opacity == 1.0
    assert layer.image.getpixel((0, 0)) == (255, 0, 0, 255)
