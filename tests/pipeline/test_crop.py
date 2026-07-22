from PIL import Image

from src.pipeline.crop import crop_box


def test_crop_box_normal_box_returns_cropped_region():
    image = Image.new("RGB", (100, 100))
    cropped = crop_box(image, (10, 10, 50, 50))
    assert cropped.size == (40, 40)


def test_crop_box_touching_boundary_returns_full_region():
    image = Image.new("RGB", (100, 100))
    cropped = crop_box(image, (50, 50, 100, 100))
    assert cropped.size == (50, 50)


def test_crop_box_exceeding_boundary_gets_clamped():
    image = Image.new("RGB", (100, 100))
    cropped = crop_box(image, (80, 80, 150, 150))
    assert cropped.size == (20, 20)


def test_crop_box_degenerate_after_clamp_returns_none():
    image = Image.new("RGB", (100, 100))
    cropped = crop_box(image, (150, 150, 200, 200))
    assert cropped is None


def test_crop_box_padding_ratio_expands_by_box_dimensions():
    image = Image.new("RGB", (100, 100))
    cropped = crop_box(image, (20, 20, 40, 40), padding_ratio=0.5)
    assert cropped.size == (40, 40)
