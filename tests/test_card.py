import pytest
from PIL import Image

from layerkit.card import (
    CARD_HEIGHT,
    CARD_WIDTH,
    IMAGE_HEIGHT,
    IMAGE_WIDTH,
    _cover_resize,
    _round_bottom_corners,
    extract_dark_bg_color,
    generate_card,
    generate_cards_from_dir,
    parse_mapping_file,
)


def _solid_photo(color=(220, 60, 30), size=(800, 500)):
    return Image.new("RGB", size, color)


def test_extract_dark_bg_color_is_dark_and_hue_matched():
    photo = _solid_photo((220, 60, 30))  # a saturated red-orange
    r, g, b = extract_dark_bg_color(photo)
    # dark: no channel should be near full brightness
    assert max(r, g, b) < 130
    # hue-matched: red channel should still dominate, like the source color
    assert r >= g and r >= b


def test_cover_resize_fills_target_and_crops():
    photo = _solid_photo(size=(1000, 400))  # wide photo
    fitted = _cover_resize(photo, (300, 450))  # tall target
    assert fitted.size == (300, 450)


def test_round_bottom_corners_keeps_top_square_and_cuts_bottom():
    img = Image.new("RGBA", (100, 100), (255, 0, 0, 255))
    rounded = _round_bottom_corners(img, radius=30)
    # top-left corner: still fully opaque (square, not rounded)
    assert rounded.getpixel((0, 0))[3] == 255
    # bottom-left corner: cut away by the rounding (transparent)
    assert rounded.getpixel((0, 99))[3] == 0
    # bottom-center: still opaque (inside the rounded rect, away from the corner)
    assert rounded.getpixel((50, 99))[3] == 255


def test_generate_card_produces_expected_size(tmp_path):
    photo_path = tmp_path / "photo.jpg"
    _solid_photo(size=(600, 900)).save(photo_path)

    out_path = tmp_path / "card.png"
    result_path, bg = generate_card(
        str(photo_path), cn_text="标题", en_text="Subtitle", out_path=str(out_path), scale=1
    )

    assert result_path == str(out_path)
    with Image.open(out_path) as img:
        assert img.size == (CARD_WIDTH, CARD_HEIGHT)
    assert len(bg) == 3


def test_generate_card_respects_forced_bg_color(tmp_path):
    photo_path = tmp_path / "photo.jpg"
    _solid_photo().save(photo_path)
    out_path = tmp_path / "card.png"

    _, bg = generate_card(
        str(photo_path), cn_text="x", out_path=str(out_path), scale=1, bg_color=(10, 20, 30)
    )
    assert bg == (10, 20, 30)

    with Image.open(out_path) as img:
        # bottom-right corner of the canvas is pure background, no image/text there
        assert img.convert("RGB").getpixel((CARD_WIDTH - 1, CARD_HEIGHT - 1)) == (10, 20, 30)


def test_parse_mapping_file_reads_rows_and_skips_comments(tmp_path):
    mapping_path = tmp_path / "mapping.txt"
    mapping_path.write_text(
        "# comment\n"
        "\n"
        "photo1.jpg | 身高 | Height\n"
        "photo2.jpg | 只有中文\n",
        encoding="utf-8",
    )
    rows = parse_mapping_file(str(mapping_path))
    assert rows == [
        {"image": "photo1.jpg", "cn": "身高", "en": "Height"},
        {"image": "photo2.jpg", "cn": "只有中文", "en": ""},
    ]


def test_parse_mapping_file_rejects_malformed_line(tmp_path):
    mapping_path = tmp_path / "mapping.txt"
    mapping_path.write_text("just_a_filename_no_pipe\n", encoding="utf-8")
    with pytest.raises(ValueError):
        parse_mapping_file(str(mapping_path))


def test_generate_cards_from_dir_processes_mapping_and_skips_missing(tmp_path):
    images_dir = tmp_path / "origin_cards"
    images_dir.mkdir()
    _solid_photo().save(images_dir / "a.jpg")

    (images_dir / "mapping.txt").write_text(
        "a.jpg | 甲 | A\n"
        "missing.jpg | 乙 | B\n",
        encoding="utf-8",
    )

    out_dir = tmp_path / "cards"
    results = generate_cards_from_dir(str(images_dir), out_dir=str(out_dir), scale=1)

    assert len(results) == 1  # the missing.jpg row was skipped
    assert (out_dir / "a.png").exists()
