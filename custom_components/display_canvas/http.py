"""HTTP endpoints for Display Canvas."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
import hmac
from io import BytesIO, StringIO
from pathlib import Path
import time

from aiohttp import web
import PIL.Image

from homeassistant.components import camera, media_source
from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_AERIAL_MIN_RESOLUTION,
    CONF_AERIAL_ORIENTATION,
    CONF_OVERFLIGHT_MIN_RESOLUTION,
    CONF_OVERFLIGHT_ORIENTATION,
    DATA_ENTRIES,
    DOMAIN,
    ORIENTATION_ANY,
    ORIENTATION_LANDSCAPE,
    ORIENTATION_PORTRAIT,
    RESOLUTION_1080P,
    RESOLUTION_1440P,
    RESOLUTION_4K,
    RESOLUTION_720P,
    RESOLUTION_ANY,
    TARGET_AERIAL,
    TARGET_OVERFLIGHT,
)
from .feed import feed_base_url
from .library import camera_entity_id, media_source_id

MAX_IMAGES = 500

MIN_RESOLUTIONS = {
    RESOLUTION_720P: (1280, 720),
    RESOLUTION_1080P: (1920, 1080),
    RESOLUTION_1440P: (2560, 1440),
    RESOLUTION_4K: (3840, 2160),
}


def _display_dimensions(
    image: PIL.Image.Image,
) -> tuple[int, int]:
    """Return dimensions after accounting for EXIF rotation."""

    width, height = image.size
    orientation = image.getexif().get(274)

    if orientation in {5, 6, 7, 8}:
        return height, width

    return width, height


@lru_cache(maxsize=2048)
def _cached_file_dimensions(
    path: str,
    _mtime_ns: int,
    _size: int,
) -> tuple[int, int] | None:
    """Read and cache dimensions for an unchanged local file."""

    try:
        with PIL.Image.open(path) as image:
            return _display_dimensions(image)
    except OSError:
        return None


def _dimensions_from_file(
    path: str | Path,
) -> tuple[int, int] | None:
    """Read image dimensions from a local file."""

    try:
        file_path = Path(path)
        stat = file_path.stat()
    except OSError:
        return None

    return _cached_file_dimensions(
        str(file_path),
        stat.st_mtime_ns,
        stat.st_size,
    )


def _dimensions_from_bytes(
    content: bytes,
) -> tuple[int, int] | None:
    """Read image dimensions from image bytes."""

    try:
        with PIL.Image.open(BytesIO(content)) as image:
            return _display_dimensions(image)
    except OSError:
        return None


async def _async_image_dimensions(
    hass: HomeAssistant,
    image,
) -> tuple[int, int] | None:
    """Return dimensions for a published image."""

    camera_id = camera_entity_id(
        image.media_content_id
    )

    if camera_id is not None:
        try:
            snapshot = await camera.async_get_image(
                hass,
                camera_id,
            )
        except HomeAssistantError:
            return None

        return await hass.async_add_executor_job(
            _dimensions_from_bytes,
            snapshot.content,
        )

    try:
        resolved = await media_source.async_resolve_media(
            hass,
            image.media_content_id,
            None,
        )
    except HomeAssistantError:
        return None

    if resolved.path is None:
        return None

    return await hass.async_add_executor_job(
        _dimensions_from_file,
        resolved.path,
    )


def _matches_image_filter(
    dimensions: tuple[int, int],
    orientation: str,
    resolution: str,
) -> bool:
    """Return whether dimensions match feed filters."""

    width, height = dimensions

    if (
        orientation == ORIENTATION_LANDSCAPE
        and width <= height
    ):
        return False

    if (
        orientation == ORIENTATION_PORTRAIT
        and height <= width
    ):
        return False

    if resolution == RESOLUTION_ANY:
        return True

    minimum = MIN_RESOLUTIONS.get(resolution)

    if minimum is None:
        return True

    required_long, required_short = minimum

    return (
        max(width, height) >= required_long
        and min(width, height) >= required_short
    )


@dataclass(frozen=True, slots=True)
class DisplayCanvasImage:
    """Represent an image published by Display Canvas."""

    title: str
    media_content_id: str
    media_content_type: str


async def _async_image_version(
    hass: HomeAssistant,
    image,
) -> str | None:
    """Return a cache version for an image."""

    if camera_entity_id(image.media_content_id) is not None:
        # Cameras may change without their HA state changing.
        # Rotate the cache key every minute.
        return f"c{int(time.time() // 60)}"

    try:
        resolved = await media_source.async_resolve_media(
            hass,
            image.media_content_id,
            None,
        )
    except HomeAssistantError:
        return None

    if resolved.path is None:
        return None

    try:
        stat = await hass.async_add_executor_job(
            Path(resolved.path).stat
        )
    except OSError:
        return None

    return f"f{stat.st_mtime_ns:x}-{stat.st_size:x}"


async def _async_image_url(
    hass: HomeAssistant,
    base: str,
    token: str,
    image,
) -> str:
    """Build a cache-aware public image URL."""

    url = (
        f"{base}/api/display_canvas/{token}/media/"
        f"{_image_id(image.media_content_id)}"
        f"{_image_suffix(image)}"
    )

    if version := await _async_image_version(
        hass,
        image,
    ):
        return f"{url}?v={version}"

    return url


def _entry_for_token(
    hass: HomeAssistant,
    token: str,
) -> ConfigEntry | None:
    """Find the loaded Display Canvas entry for a token."""
    entries = hass.data.get(DOMAIN, {}).get(DATA_ENTRIES, {})

    for entry in entries.values():
        expected = entry.data.get(CONF_ACCESS_TOKEN, "")
        if expected and hmac.compare_digest(expected, token):
            return entry

    return None


def _image_id(media_content_id: str) -> str:
    """Generate a stable public ID for a media item."""
    return sha256(media_content_id.encode()).hexdigest()[:24]


def _image_suffix(image) -> str:
    """Return a useful file extension for a media item."""
    suffix = Path(image.title).suffix.lower()

    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        return suffix

    return {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }.get(image.media_content_type, ".jpg")


async def _async_images_from_source(
    hass: HomeAssistant,
    source_id: str,
) -> list:
    """Recursively collect images from a media source."""
    if (entity_id := camera_entity_id(source_id)) is not None:
        state = hass.states.get(entity_id)

        if state is None:
            return []

        title = state.attributes.get(
            "friendly_name",
            entity_id,
        )

        return [
            DisplayCanvasImage(
                title=f"{title}.jpg",
                media_content_id=source_id,
                media_content_type="image/jpeg",
            )
        ]

    pending = [source_id]
    visited: set[str] = set()
    images = []

    while pending and len(images) < MAX_IMAGES:
        current = pending.pop()

        if current in visited:
            continue

        visited.add(current)

        try:
            browsed = await media_source.async_browse_media(
                hass,
                current,
            )
        except BrowseError:
            continue

        for child in browsed.children or []:
            if child.can_expand:
                pending.append(child.media_content_id)
                continue

            content_type = child.media_content_type or ""

            if (
                child.can_play
                and isinstance(content_type, str)
                and content_type.startswith("image/")
            ):
                images.append(child)

                if len(images) >= MAX_IMAGES:
                    break

    return sorted(
        images,
        key=lambda item: item.title.casefold(),
    )


def _feed_filters(
    entry: ConfigEntry,
    target: str,
) -> tuple[str, str]:
    """Return orientation and resolution filters."""

    if target == TARGET_OVERFLIGHT:
        return (
            entry.options.get(
                CONF_OVERFLIGHT_ORIENTATION,
                ORIENTATION_ANY,
            ),
            entry.options.get(
                CONF_OVERFLIGHT_MIN_RESOLUTION,
                RESOLUTION_ANY,
            ),
        )

    return (
        entry.options.get(
            CONF_AERIAL_ORIENTATION,
            ORIENTATION_ANY,
        ),
        entry.options.get(
            CONF_AERIAL_MIN_RESOLUTION,
            RESOLUTION_ANY,
        ),
    )


async def _async_filter_images(
    hass: HomeAssistant,
    entry: ConfigEntry,
    target: str,
    images: list,
) -> list:
    """Apply configured filters to a feed."""

    orientation, resolution = _feed_filters(
        entry,
        target,
    )

    if (
        orientation == ORIENTATION_ANY
        and resolution == RESOLUTION_ANY
    ):
        return images

    filtered = []

    for image in images:
        dimensions = await _async_image_dimensions(
            hass,
            image,
        )

        if dimensions is None:
            continue

        if _matches_image_filter(
            dimensions,
            orientation,
            resolution,
        ):
            filtered.append(image)

    return filtered


async def async_feed_image_counts(
    hass: HomeAssistant,
    entry: ConfigEntry,
    target: str,
) -> tuple[int, int]:
    """Return published and total image counts for a feed."""

    images = await _async_images_from_source(
        hass,
        media_source_id(entry, target),
    )

    filtered = await _async_filter_images(
        hass,
        entry,
        target,
        images,
    )

    return len(filtered), len(images)


async def _async_images(
    hass: HomeAssistant,
    entry: ConfigEntry,
    target: str,
) -> list:
    """Return published images for a target."""
    images = await _async_images_from_source(
        hass,
        media_source_id(entry, target),
    )

    return await _async_filter_images(
        hass,
        entry,
        target,
        images,
    )


async def _async_find_image(
    hass: HomeAssistant,
    entry: ConfigEntry,
    image_id: str,
):
    """Find an image published by either target."""
    image_id = image_id.split(".", 1)[0]

    checked_sources: set[str] = set()

    for target in (
        TARGET_OVERFLIGHT,
        TARGET_AERIAL,
    ):
        source_id = media_source_id(entry, target)

        if source_id in checked_sources:
            continue

        checked_sources.add(source_id)

        for image in await _async_images_from_source(
            hass,
            source_id,
        ):
            if hmac.compare_digest(
                _image_id(image.media_content_id),
                image_id,
            ):
                return image

    return None


class DisplayCanvasOverflightView(HomeAssistantView):
    """Serve an Overflight JSON feed."""

    url = "/api/display_canvas/{token}/overflight.json"
    name = "api:display_canvas:overflight"
    requires_auth = False

    async def get(
        self,
        request: web.Request,
        token: str,
    ) -> web.Response:
        """Return images formatted for Projectivy Overflight."""
        hass: HomeAssistant = request.app[KEY_HASS]

        if (entry := _entry_for_token(hass, token)) is None:
            raise web.HTTPNotFound

        images = await _async_images(
            hass,
            entry,
            TARGET_OVERFLIGHT,
        )
        base = feed_base_url(
            hass,
            entry,
            fallback=f"{request.scheme}://{request.host}",
        )

        result = []

        for image in images:
            result.append(
                {
                    "location": "Display Canvas",
                    "title": image.title,
                    "author": "Home Assistant",
                    "url_img": await _async_image_url(
                        hass,
                        base,
                        token,
                        image,
                    ),
                }
            )

        return self.json(
            result,
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )


class DisplayCanvasAerialView(HomeAssistantView):
    """Serve an Aerial Views CSV feed."""

    url = "/api/display_canvas/{token}/aerial.csv"
    name = "api:display_canvas:aerial"
    requires_auth = False

    async def get(
        self,
        request: web.Request,
        token: str,
    ) -> web.Response:
        """Return images formatted for Aerial Views."""
        hass: HomeAssistant = request.app[KEY_HASS]

        if (entry := _entry_for_token(hass, token)) is None:
            raise web.HTTPNotFound

        images = await _async_images(
            hass,
            entry,
            TARGET_AERIAL,
        )
        base = feed_base_url(
            hass,
            entry,
            fallback=f"{request.scheme}://{request.host}",
        )

        output = StringIO()
        writer = csv.writer(output)

        writer.writerow(["url", "description"])

        for image in images:
            writer.writerow(
                [
                    await _async_image_url(
                        hass,
                        base,
                        token,
                        image,
                    ),
                    image.title,
                ]
            )

        return web.Response(
            text=output.getvalue(),
            content_type="text/csv",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )


class DisplayCanvasMediaView(HomeAssistantView):
    """Serve a published Display Canvas image."""

    url = "/api/display_canvas/{token}/media/{image_id}"
    name = "api:display_canvas:media"
    requires_auth = False

    async def get(
        self,
        request: web.Request,
        token: str,
        image_id: str,
    ) -> web.StreamResponse:
        """Return an image from a published source."""
        hass: HomeAssistant = request.app[KEY_HASS]

        if (entry := _entry_for_token(hass, token)) is None:
            raise web.HTTPNotFound

        image = await _async_find_image(
            hass,
            entry,
            image_id,
        )

        if image is None:
            raise web.HTTPNotFound

        camera_id = camera_entity_id(
            image.media_content_id
        )

        if camera_id is not None:
            try:
                snapshot = await camera.async_get_image(
                    hass,
                    camera_id,
                )
            except HomeAssistantError as err:
                raise web.HTTPServiceUnavailable(
                    reason="Unable to get camera image"
                ) from err

            return web.Response(
                body=snapshot.content,
                content_type=snapshot.content_type,
                headers={
                    "Cache-Control": (
                        "no-store, no-cache, must-revalidate"
                    ),
                    "Pragma": "no-cache",
                    "Expires": "0",
                },
            )

        resolved = await media_source.async_resolve_media(
            hass,
            image.media_content_id,
            None,
        )

        if resolved.path is None:
            raise web.HTTPNotFound(
                reason=(
                    "This media source cannot yet be proxied "
                    "by Display Canvas"
                )
            )

        return web.FileResponse(
            resolved.path,
            headers={
                "Cache-Control": (
                    "no-store, no-cache, must-revalidate"
                ),
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )


def async_register_http_views(hass: HomeAssistant) -> None:
    """Register Display Canvas HTTP endpoints."""
    hass.http.register_view(DisplayCanvasOverflightView)
    hass.http.register_view(DisplayCanvasAerialView)
    hass.http.register_view(DisplayCanvasMediaView)
