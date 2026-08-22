import pytest
from PIL import Image

from layerkit import Document, Layer


def test_composite_flat_opaque_layer():
    doc = Document(4, 4, background=(0, 0, 0, 0))
    doc.add_layer(Layer(Image.new("RGBA", (4, 4), (10, 20, 30, 255)), name="A"))
    result = doc.composite()
    assert result.size == (4, 4)
    assert result.getpixel((0, 0)) == (10, 20, 30, 255)


def test_layer_management_add_remove_rename():
    doc = Document(4, 4)
    doc.new_layer("A")
    doc.new_layer("B")
    assert [l.name for l in doc.layers] == ["A", "B"]

    doc.rename_layer("A", "Background")
    assert doc.get_layer(0).name == "Background"

    doc.remove_layer("B")
    assert [l.name for l in doc.layers] == ["Background"]


def test_move_layer_reorders_stack():
    doc = Document(4, 4)
    doc.new_layer("A")
    doc.new_layer("B")
    doc.new_layer("C")
    doc.move_layer("A", 2)
    assert [l.name for l in doc.layers] == ["B", "C", "A"]


def test_move_layer_up_and_down():
    doc = Document(4, 4)
    doc.new_layer("A")
    doc.new_layer("B")
    doc.move_layer_up("A")
    assert [l.name for l in doc.layers] == ["B", "A"]
    doc.move_layer_down("A")
    assert [l.name for l in doc.layers] == ["A", "B"]


def test_hidden_layer_excluded_from_composite():
    doc = Document(2, 2, background=(255, 255, 255, 255))
    doc.add_layer(Layer(Image.new("RGBA", (2, 2), (0, 0, 0, 255)), name="Black"))
    doc.set_visible("Black", False)
    result = doc.composite()
    assert result.getpixel((0, 0)) == (255, 255, 255, 255)


def test_opacity_blends_toward_backdrop():
    doc = Document(1, 1, background=(0, 0, 0, 255))
    doc.add_layer(Layer(Image.new("RGBA", (1, 1), (255, 255, 255, 255)), name="White", opacity=0.5))
    result = doc.composite()
    r, g, b, a = result.getpixel((0, 0))
    assert 120 <= r <= 135  # ~50% gray, allow rounding slack


def test_layer_offset_is_clipped_to_canvas():
    doc = Document(4, 4, background=(0, 0, 0, 255))
    layer = Layer(Image.new("RGBA", (4, 4), (255, 0, 0, 255)), name="Offset", x=2, y=2)
    doc.add_layer(layer)
    result = doc.composite()
    assert result.getpixel((0, 0)) == (0, 0, 0, 255)  # untouched corner
    assert result.getpixel((3, 3)) == (255, 0, 0, 255)  # inside the offset layer


def test_get_layer_missing_name_raises():
    doc = Document(4, 4)
    with pytest.raises(KeyError):
        doc.get_layer("nope")


def test_export_roundtrip(tmp_path):
    doc = Document(3, 3, background=(1, 2, 3, 255))
    out_file = tmp_path / "out.png"
    doc.export(str(out_file))
    assert out_file.exists()
    with Image.open(out_file) as img:
        assert img.size == (3, 3)
