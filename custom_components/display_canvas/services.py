"""Actions for Display Canvas."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError

from .const import (
    ATTR_LIBRARY,
    ATTR_MEDIA_SOURCE,
    ATTR_TARGET,
    CONF_AERIAL_LIBRARY,
    CONF_AERIAL_SOURCE,
    CONF_LIBRARIES,
    CONF_OVERFLIGHT_LIBRARY,
    CONF_OVERFLIGHT_SOURCE,
    DATA_ENTRIES,
    DOMAIN,
    SERVICE_REMOVE_LIBRARY,
    SERVICE_SAVE_LIBRARY,
    SERVICE_SET_LIBRARY,
    SERVICE_SET_SOURCE,
    TARGET_AERIAL,
    TARGET_ALL,
    TARGET_OVERFLIGHT,
)
from .library import find_library_name, libraries


TARGET_SCHEMA = vol.In(
    [
        TARGET_OVERFLIGHT,
        TARGET_AERIAL,
        TARGET_ALL,
    ]
)


def _validate_media_source(value: Any) -> dict[str, Any]:
    """Validate a Home Assistant media selector value."""
    if not isinstance(value, dict):
        raise vol.Invalid("Media source must be an object")

    media_content_id = value.get("media_content_id")

    if not isinstance(media_content_id, str) or not media_content_id:
        raise vol.Invalid(
            "Media source must contain media_content_id"
        )

    return value


def _validate_library_name(value: Any) -> str:
    """Validate and normalize a library name."""
    if not isinstance(value, str):
        raise vol.Invalid("Library name must be text")

    value = value.strip()

    if not value:
        raise vol.Invalid("Library name cannot be empty")

    if len(value) > 64:
        raise vol.Invalid("Library name cannot exceed 64 characters")

    return value


SET_SOURCE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_TARGET): TARGET_SCHEMA,
        vol.Required(ATTR_MEDIA_SOURCE): _validate_media_source,
    }
)

SAVE_LIBRARY_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_LIBRARY): _validate_library_name,
        vol.Required(ATTR_MEDIA_SOURCE): _validate_media_source,
    }
)

REMOVE_LIBRARY_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_LIBRARY): _validate_library_name,
    }
)

SET_LIBRARY_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_TARGET): TARGET_SCHEMA,
        vol.Required(ATTR_LIBRARY): _validate_library_name,
    }
)


def _entry(hass: HomeAssistant) -> ConfigEntry:
    """Return the loaded Display Canvas config entry."""
    entries = hass.data.get(DOMAIN, {}).get(
        DATA_ENTRIES,
        {},
    )

    if not entries:
        raise ServiceValidationError(
            "Display Canvas is not loaded"
        )

    return next(iter(entries.values()))



async def _async_update_options(
    hass: HomeAssistant,
    entry: ConfigEntry,
    options: dict,
) -> None:
    """Store options and reload Display Canvas."""
    hass.config_entries.async_update_entry(
        entry,
        options=options,
    )

    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register Display Canvas actions."""

    async def async_set_source(call: ServiceCall) -> None:
        """Change the raw media source used by a feed."""
        entry = _entry(hass)

        target = call.data[ATTR_TARGET]
        media_source = call.data[ATTR_MEDIA_SOURCE]

        options = dict(entry.options)

        if target in (TARGET_OVERFLIGHT, TARGET_ALL):
            options[CONF_OVERFLIGHT_SOURCE] = media_source
            options.pop(CONF_OVERFLIGHT_LIBRARY, None)

        if target in (TARGET_AERIAL, TARGET_ALL):
            options[CONF_AERIAL_SOURCE] = media_source
            options.pop(CONF_AERIAL_LIBRARY, None)

        await _async_update_options(
            hass,
            entry,
            options,
        )

    async def async_save_library(call: ServiceCall) -> None:
        """Create or update a named library."""
        entry = _entry(hass)

        requested_name = call.data[ATTR_LIBRARY]
        media_source = call.data[ATTR_MEDIA_SOURCE]

        configured = libraries(entry)

        existing_name = find_library_name(
            entry,
            requested_name,
        )

        name = existing_name or requested_name

        configured[name] = media_source

        options = dict(entry.options)
        options[CONF_LIBRARIES] = configured

        await _async_update_options(
            hass,
            entry,
            options,
        )

    async def async_remove_library(call: ServiceCall) -> None:
        """Remove a named library."""
        entry = _entry(hass)

        requested_name = call.data[ATTR_LIBRARY]

        name = find_library_name(
            entry,
            requested_name,
        )

        if name is None:
            raise ServiceValidationError(
                f"Library '{requested_name}' does not exist"
            )

        if entry.options.get(CONF_OVERFLIGHT_LIBRARY) == name:
            raise ServiceValidationError(
                f"Library '{name}' is currently used by Overflight"
            )

        if entry.options.get(CONF_AERIAL_LIBRARY) == name:
            raise ServiceValidationError(
                f"Library '{name}' is currently used by Aerial Views"
            )

        configured = libraries(entry)
        configured.pop(name)

        options = dict(entry.options)
        options[CONF_LIBRARIES] = configured

        await _async_update_options(
            hass,
            entry,
            options,
        )

    async def async_set_library(call: ServiceCall) -> None:
        """Select a named library for one or more feeds."""
        entry = _entry(hass)

        target = call.data[ATTR_TARGET]
        requested_name = call.data[ATTR_LIBRARY]

        name = find_library_name(
            entry,
            requested_name,
        )

        if name is None:
            raise ServiceValidationError(
                f"Library '{requested_name}' does not exist"
            )

        options = dict(entry.options)

        if target in (TARGET_OVERFLIGHT, TARGET_ALL):
            options[CONF_OVERFLIGHT_LIBRARY] = name

        if target in (TARGET_AERIAL, TARGET_ALL):
            options[CONF_AERIAL_LIBRARY] = name

        await _async_update_options(
            hass,
            entry,
            options,
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_SOURCE,
        async_set_source,
        schema=SET_SOURCE_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SAVE_LIBRARY,
        async_save_library,
        schema=SAVE_LIBRARY_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_LIBRARY,
        async_remove_library,
        schema=REMOVE_LIBRARY_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_LIBRARY,
        async_set_library,
        schema=SET_LIBRARY_SCHEMA,
    )
