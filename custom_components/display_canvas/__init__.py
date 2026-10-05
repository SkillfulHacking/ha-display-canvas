"""Display Canvas integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DATA_ENTRIES, DOMAIN
from .http import async_register_http_views


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Set up Display Canvas from a config entry."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    entries = domain_data.setdefault(DATA_ENTRIES, {})

    entries[entry.entry_id] = entry

    if not domain_data.get("http_registered"):
        async_register_http_views(hass)
        domain_data["http_registered"] = True

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Unload a Display Canvas config entry."""
    entries = hass.data.get(DOMAIN, {}).get(DATA_ENTRIES, {})
    entries.pop(entry.entry_id, None)

    return True
