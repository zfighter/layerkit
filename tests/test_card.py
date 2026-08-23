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
    remove_watermark,
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


def test_parse_mapping_file_accepts_fullwidth_pipe(tmp_path):
    # Chinese IMEs often auto-substitute "|" with the fullwidth "｜" (U+FF5C).
    mapping_path = tmp_path / "mapping.txt"
    mapping_path.write_text("photo.jpg｜ 音乐家 ｜Musicians\n", encoding="utf-8")
    rows = parse_mapping_file(str(mapping_path))
    assert rows == [{"image": "photo.jpg", "cn": "音乐家", "en": "Musicians"}]


def test_parse_mapping_file_rejects_malformed_line(tmp_path):
    mapping_path = tmp_path / "mapping.txt"
    mapping_path.write_text("just_a_filename_no_pipe\n", encoding="utf-8")
    with pytest.raises(ValueError):
        parse_mapping_file(str(mapping_path))


def test_remove_watermark_erases_corner_patch():
    # Plain background with a contrasting "watermark" stamped in the corner
    # region remove_watermark targets by default.
    img = Image.new("RGB", (400, 300), (240, 235, 210))
    x0, y0 = int(400 * 0.75), int(300 * 0.92)
    for x in range(x0, 400):
        for y in range(y0, 300):
            img.putpixel((x, y), (0, 0, 0))

    cleaned = remove_watermark(img)
    # center of the patched region should now be close to the surrounding
    # background color rather than the stamped black.
    r, g, b = cleaned.getpixel(((x0 + 400) // 2, (y0 + 300) // 2))
    assert (r, g, b) != (0, 0, 0)
    assert abs(r - 240) < 40 and abs(g - 235) < 40 and abs(b - 210) < 40


def test_remove_watermark_preserves_alpha_channel():
    img = Image.new("RGBA", (200, 200), (100, 150, 200, 128))
    cleaned = remove_watermark(img)
    assert cleaned.mode == "RGBA"
    assert cleaned.getpixel((5, 5))[3] == 128


def test_generate_card_skips_watermark_removal_when_disabled(tmp_path, monkeypatch):
    import layerkit.card as card_module

    def _boom(*args, **kwargs):
        raise AssertionError("remove_watermark should not have been called")

    monkeypatch.setattr(card_module, "remove_watermark", _boom)

    photo_path = tmp_path / "photo.jpg"
    _solid_photo().save(photo_path)
    out_path = tmp_path / "card.png"

    # Should not raise, proving remove_watermark was skipped.
    generate_card(str(photo_path), out_path=str(out_path), scale=1, remove_watermark_flag=False)
    assert out_path.exists()


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
