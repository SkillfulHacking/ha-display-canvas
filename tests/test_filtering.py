"""Regression tests for Display Canvas image filtering."""

from PIL import Image
import pytest

from custom_components.display_canvas.const import (
    ORIENTATION_ANY,
    ORIENTATION_LANDSCAPE,
    ORIENTATION_PORTRAIT,
    RESOLUTION_1080P,
    RESOLUTION_1440P,
    RESOLUTION_4K,
    RESOLUTION_720P,
    RESOLUTION_ANY,
)
from custom_components.display_canvas.http import (
    _display_dimensions,
    _matches_image_filter,
)


@pytest.mark.parametrize(
    ("resolution", "expected"),
    [
        (RESOLUTION_ANY, True),
        (RESOLUTION_720P, True),
        (RESOLUTION_1080P, True),
        (RESOLUTION_1440P, False),
        (RESOLUTION_4K, False),
    ],
)
def test_resolution_thresholds(
    resolution: str,
    expected: bool,
) -> None:
    """A 1920x1080 image should meet 1080p but not 1440p."""
    assert (
        _matches_image_filter(
            (1920, 1080),
            ORIENTATION_LANDSCAPE,
            resolution,
        )
        is expected
    )


def test_landscape_filter() -> None:
    """Landscape accepts landscape and rejects portrait."""
    assert _matches_image_filter(
        (1920, 1080),
        ORIENTATION_LANDSCAPE,
        RESOLUTION_ANY,
    )
    assert not _matches_image_filter(
        (1080, 1920),
        ORIENTATION_LANDSCAPE,
        RESOLUTION_ANY,
    )


def test_portrait_filter() -> None:
    """Portrait accepts portrait and rejects landscape."""
    assert _matches_image_filter(
        (1080, 1920),
        ORIENTATION_PORTRAIT,
        RESOLUTION_ANY,
    )
    assert not _matches_image_filter(
        (1920, 1080),
        ORIENTATION_PORTRAIT,
        RESOLUTION_ANY,
    )


def test_square_only_matches_any_orientation() -> None:
    """Square images are neither landscape nor portrait."""
    assert _matches_image_filter(
        (1600, 1600),
        ORIENTATION_ANY,
        RESOLUTION_ANY,
    )
    assert not _matches_image_filter(
        (1600, 1600),
        ORIENTATION_LANDSCAPE,
        RESOLUTION_ANY,
    )
    assert not _matches_image_filter(
        (1600, 1600),
        ORIENTATION_PORTRAIT,
        RESOLUTION_ANY,
    )


def test_resolution_uses_long_and_short_edges() -> None:
    """Resolution filtering should not require a 16:9 aspect ratio."""
    assert _matches_image_filter(
        (2400, 1600),
        ORIENTATION_LANDSCAPE,
        RESOLUTION_1080P,
    )


def test_exif_rotation_swaps_dimensions() -> None:
    """EXIF orientation should affect displayed dimensions."""
    image = Image.new("RGB", (1080, 1920))
    image.getexif()[274] = 6

    assert _display_dimensions(image) == (1920, 1080)
