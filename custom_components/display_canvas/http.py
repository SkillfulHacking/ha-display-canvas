"""HTTP endpoints for Display Canvas."""

from __future__ import annotations

import csv
from hashlib import sha256
import hmac
from io import StringIO
from pathlib import Path

from aiohttp import web

from homeassistant.components import media_source
from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_MEDIA_SOURCE,
    DATA_ENTRIES,
    DOMAIN,
)

MAX_IMAGES = 500


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


def _media_source_id(entry: ConfigEntry) -> str:
    """Return the configured HA media source ID."""
    selected = entry.options.get(
        CONF_MEDIA_SOURCE,
        entry.data[CONF_MEDIA_SOURCE],
    )

    if isinstance(selected, dict):
        return selected["media_content_id"]

    return selected


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


def _base_url(request: web.Request) -> str:
    """Build the URL base used by the requesting display."""
    return f"{request.scheme}://{request.host}"


async def _async_images(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> list:
    """Recursively collect images from the configured media source."""
    pending = [_media_source_id(entry)]
    visited: set[str] = set()
    images = []

    while pending and len(images) < MAX_IMAGES:
        current = pending.pop()

        if current in visited:
            continue

        visited.add(current)

        browsed = await media_source.async_browse_media(hass, current)

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

    return sorted(images, key=lambda item: item.title.casefold())


async def _async_find_image(
    hass: HomeAssistant,
    entry: ConfigEntry,
    image_id: str,
):
    """Find a published image by its stable ID."""
    image_id = image_id.split(".", 1)[0]

    for image in await _async_images(hass, entry):
        if hmac.compare_digest(_image_id(image.media_content_id), image_id):
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

        images = await _async_images(hass, entry)
        base = _base_url(request)

        result = [
            {
                "location": "Display Canvas",
                "title": image.title,
                "author": "Home Assistant",
                "url_img": (
                    f"{base}/api/display_canvas/{token}/media/"
                    f"{_image_id(image.media_content_id)}"
                    f"{_image_suffix(image)}"
                ),
            }
            for image in images
        ]

        return self.json(result)


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

        images = await _async_images(hass, entry)
        base = _base_url(request)

        output = StringIO()
        writer = csv.writer(output)

        writer.writerow(["url", "description"])

        for image in images:
            writer.writerow(
                [
                    (
                        f"{base}/api/display_canvas/{token}/media/"
                        f"{_image_id(image.media_content_id)}"
                    f"{_image_suffix(image)}"
                    ),
                    image.title,
                ]
            )

        return web.Response(
            text=output.getvalue(),
            content_type="text/csv",
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
        """Return an image from the configured collection."""
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

        resolved = await media_source.async_resolve_media(
            hass,
            image.media_content_id,
            None,
        )

        if resolved.path is None:
            raise web.HTTPNotFound(
                reason="This media source cannot yet be proxied by Display Canvas"
            )

        return web.FileResponse(resolved.path)


def async_register_http_views(hass: HomeAssistant) -> None:
    """Register Display Canvas HTTP endpoints."""
    hass.http.register_view(DisplayCanvasOverflightView)
    hass.http.register_view(DisplayCanvasAerialView)
    hass.http.register_view(DisplayCanvasMediaView)
