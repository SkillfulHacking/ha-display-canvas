"""Feed URL helpers for Display Canvas."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .const import CONF_ACCESS_TOKEN, CONF_BASE_URL


def feed_base_url(
    hass: HomeAssistant,
    entry: ConfigEntry,
    fallback: str | None = None,
) -> str:
    """Return the base URL used in published feeds."""

    if configured := entry.options.get(CONF_BASE_URL):
        return configured.rstrip("/")

    try:
        return get_url(
            hass,
            allow_internal=True,
            allow_external=False,
            allow_cloud=False,
            prefer_external=False,
        ).rstrip("/")
    except NoURLAvailableError:
        return (fallback or "").rstrip("/")


def feed_url(
    hass: HomeAssistant,
    entry: ConfigEntry,
    filename: str,
) -> str:
    """Return a complete Display Canvas feed URL."""

    base = feed_base_url(hass, entry)
    token = entry.data[CONF_ACCESS_TOKEN]

    if not base:
        return "Set a Base URL under General"

    return (
        f"{base}/api/display_canvas/"
        f"{token}/{filename}"
    )
