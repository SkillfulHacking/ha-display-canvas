"""Select entities for Display Canvas."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_AERIAL_LIBRARY,
    CONF_OVERFLIGHT_LIBRARY,
    TARGET_AERIAL,
    TARGET_OVERFLIGHT,
)
from .library import (
    find_library_name,
    libraries,
    selected_library,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Display Canvas select entities."""
    async_add_entities(
        [
            DisplayCanvasLibrarySelect(
                entry,
                TARGET_OVERFLIGHT,
            ),
            DisplayCanvasLibrarySelect(
                entry,
                TARGET_AERIAL,
            ),
        ]
    )


class DisplayCanvasLibrarySelect(SelectEntity):
    """Select the named library published by a Display Canvas feed."""

    _attr_should_poll = False

    def __init__(
        self,
        entry: ConfigEntry,
        target: str,
    ) -> None:
        """Initialize the library select."""
        self._entry = entry
        self._target = target

        self._attr_unique_id = (
            f"{entry.entry_id}_{target}_library"
        )

        self._attr_options = sorted(
            libraries(entry),
            key=str.casefold,
        )

        self._attr_current_option = selected_library(
            entry,
            target,
        )

        if target == TARGET_OVERFLIGHT:
            self._attr_name = "Display Canvas Overflight Library"
            self._option_key = CONF_OVERFLIGHT_LIBRARY
        else:
            self._attr_name = "Display Canvas Aerial Library"
            self._option_key = CONF_AERIAL_LIBRARY

    async def async_select_option(
        self,
        option: str,
    ) -> None:
        """Select a named library."""
        name = find_library_name(
            self._entry,
            option,
        )

        if name is None:
            raise HomeAssistantError(
                f"Display Canvas library '{option}' does not exist"
            )

        options = dict(self._entry.options)
        options[self._option_key] = name

        self.hass.config_entries.async_update_entry(
            self._entry,
            options=options,
        )

        self._attr_current_option = name
        self.async_write_ha_state()
