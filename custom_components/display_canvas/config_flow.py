"""Config flow for Display Canvas."""

from __future__ import annotations

import secrets
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_MEDIA_SOURCE,
    DOMAIN,
    NAME,
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

        schema = vol.Schema(
            {
                vol.Required(CONF_MEDIA_SOURCE): selector.MediaSelector(
                    selector.MediaSelectorConfig(
                        accept=["directory"],
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
        )
