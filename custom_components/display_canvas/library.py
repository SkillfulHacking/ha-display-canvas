"""Library helpers for Display Canvas."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry

from .const import (
    CONF_AERIAL_LIBRARY,
    CONF_AERIAL_SOURCE,
    CONF_LIBRARIES,
    CONF_MEDIA_SOURCE,
    CONF_OVERFLIGHT_LIBRARY,
    CONF_OVERFLIGHT_SOURCE,
    TARGET_AERIAL,
    TARGET_OVERFLIGHT,
)


def libraries(entry: ConfigEntry) -> dict[str, Any]:
    """Return configured named libraries."""
    return dict(entry.options.get(CONF_LIBRARIES, {}))


def find_library_name(
    entry: ConfigEntry,
    requested: str,
) -> str | None:
    """Find a library name case-insensitively."""
    requested = requested.casefold()

    for name in libraries(entry):
        if name.casefold() == requested:
            return name

    return None


def selected_library(
    entry: ConfigEntry,
    target: str,
) -> str | None:
    """Return the selected named library for a target."""
    if target == TARGET_OVERFLIGHT:
        return entry.options.get(CONF_OVERFLIGHT_LIBRARY)

    if target == TARGET_AERIAL:
        return entry.options.get(CONF_AERIAL_LIBRARY)

    raise ValueError(f"Unsupported Display Canvas target: {target}")


def default_media_source(entry: ConfigEntry):
    """Return the legacy/default configured media source."""
    return entry.options.get(
        CONF_MEDIA_SOURCE,
        entry.data[CONF_MEDIA_SOURCE],
    )


def selected_media_source(
    entry: ConfigEntry,
    target: str,
):
    """Return the effective media source for a target."""
    configured_libraries = libraries(entry)
    library_name = selected_library(entry, target)

    if library_name and library_name in configured_libraries:
        return configured_libraries[library_name]

    default_source = default_media_source(entry)

    if target == TARGET_OVERFLIGHT:
        return entry.options.get(
            CONF_OVERFLIGHT_SOURCE,
            default_source,
        )

    if target == TARGET_AERIAL:
        return entry.options.get(
            CONF_AERIAL_SOURCE,
            default_source,
        )

    raise ValueError(f"Unsupported Display Canvas target: {target}")


def media_source_id(
    entry: ConfigEntry,
    target: str,
) -> str:
    """Return the effective HA media source ID for a target."""
    selected = selected_media_source(entry, target)

    if isinstance(selected, dict):
        return selected["media_content_id"]

    return selected
