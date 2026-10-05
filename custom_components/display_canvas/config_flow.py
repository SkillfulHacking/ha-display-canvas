"""Config flow for Display Canvas."""

from __future__ import annotations

import secrets
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, OptionsFlowWithReload
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_AERIAL_SOURCE,
    CONF_MEDIA_SOURCE,
    CONF_OVERFLIGHT_SOURCE,
    DOMAIN,
    NAME,
)


def _media_selector() -> selector.MediaSelector:
    """Return a directory-only media selector."""
    return selector.MediaSelector(
        selector.MediaSelectorConfig(
            accept=["directory"],
        )
    )


class DisplayCanvasConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Display Canvas."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Set up Display Canvas."""

        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(
                title=NAME,
                data={
                    CONF_MEDIA_SOURCE: user_input[CONF_MEDIA_SOURCE],
                    CONF_ACCESS_TOKEN: secrets.token_urlsafe(32),
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MEDIA_SOURCE): _media_selector(),
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> DisplayCanvasOptionsFlow:
        """Create the options flow."""
        return DisplayCanvasOptionsFlow()


class DisplayCanvasOptionsFlow(OptionsFlowWithReload):
    """Handle Display Canvas options."""

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Manage Display Canvas options."""

        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_OVERFLIGHT_SOURCE: user_input[
                        CONF_OVERFLIGHT_SOURCE
                    ],
                    CONF_AERIAL_SOURCE: user_input[
                        CONF_AERIAL_SOURCE
                    ],
                },
            )

        default_source = self.config_entry.options.get(
            CONF_MEDIA_SOURCE,
            self.config_entry.data.get(CONF_MEDIA_SOURCE),
        )

        overflight_source = self.config_entry.options.get(
            CONF_OVERFLIGHT_SOURCE,
            default_source,
        )

        aerial_source = self.config_entry.options.get(
            CONF_AERIAL_SOURCE,
            default_source,
        )

        schema = vol.Schema(
            {
                vol.Required(CONF_OVERFLIGHT_SOURCE): _media_selector(),
                vol.Required(CONF_AERIAL_SOURCE): _media_selector(),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                schema,
                {
                    CONF_OVERFLIGHT_SOURCE: overflight_source,
                    CONF_AERIAL_SOURCE: aerial_source,
                },
            ),
        )
