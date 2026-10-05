"""Actions for Display Canvas."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError

from .const import (
    ATTR_MEDIA_SOURCE,
    ATTR_TARGET,
    CONF_AERIAL_SOURCE,
    CONF_OVERFLIGHT_SOURCE,
    DATA_ENTRIES,
    DOMAIN,
    SERVICE_SET_SOURCE,
    TARGET_AERIAL,
    TARGET_ALL,
    TARGET_OVERFLIGHT,
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


SET_SOURCE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_TARGET): vol.In(
            [
                TARGET_OVERFLIGHT,
                TARGET_AERIAL,
                TARGET_ALL,
            ]
        ),
        vol.Required(ATTR_MEDIA_SOURCE): _validate_media_source,
    }
)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register Display Canvas actions."""

    async def async_set_source(call: ServiceCall) -> None:
        """Change the media source used by a feed."""
        entries = hass.data.get(DOMAIN, {}).get(
            DATA_ENTRIES,
            {},
        )

        if not entries:
            raise ServiceValidationError(
                "Display Canvas is not loaded"
            )

        # Display Canvas currently supports a single config entry.
        entry = next(iter(entries.values()))

        target = call.data[ATTR_TARGET]
        media_source = call.data[ATTR_MEDIA_SOURCE]

        options = dict(entry.options)

        if target in (TARGET_OVERFLIGHT, TARGET_ALL):
            options[CONF_OVERFLIGHT_SOURCE] = media_source

        if target in (TARGET_AERIAL, TARGET_ALL):
            options[CONF_AERIAL_SOURCE] = media_source

        hass.config_entries.async_update_entry(
            entry,
            options=options,
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_SOURCE,
        async_set_source,
        schema=SET_SOURCE_SCHEMA,
    )
