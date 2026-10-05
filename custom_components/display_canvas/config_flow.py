"""Config flow for Display Canvas."""

from __future__ import annotations

import secrets
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import media_source
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.config_entries import ConfigEntry, OptionsFlowWithReload
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    ATTR_LIBRARY,
    ATTR_MEDIA_SOURCE,
    CONF_ACCESS_TOKEN,
    CONF_AERIAL_LIBRARY,
    CONF_AERIAL_SOURCE,
    CONF_LIBRARIES,
    CONF_MEDIA_SOURCE,
    CONF_OVERFLIGHT_LIBRARY,
    CONF_OVERFLIGHT_SOURCE,
    DOMAIN,
    NAME,
    TARGET_AERIAL,
    TARGET_OVERFLIGHT,
)
from .library import (
    camera_entity_id,
    default_media_source,
    find_library_name,
    libraries,
    normalize_media_source,
    selected_library,
)


def _media_selector() -> selector.MediaSelector:
    """Return a browsable image media selector."""
    return selector.MediaSelector(
        selector.MediaSelectorConfig(
            accept=[
                "directory",
                "image/*",
            ],
        )
    )


def _library_name(value: Any) -> str:
    """Validate a library name."""
    if not isinstance(value, str):
        raise vol.Invalid("Library name must be text")

    value = value.strip()

    if not value:
        raise vol.Invalid("Library name cannot be empty")

    if len(value) > 64:
        raise vol.Invalid("Library name cannot exceed 64 characters")

    return value


def _library_names(entry: ConfigEntry) -> list[str]:
    """Return sorted configured library names."""
    return sorted(
        libraries(entry),
        key=str.casefold,
    )


class DisplayCanvasConfigFlow(
    config_entries.ConfigFlow,
    domain=DOMAIN,
):
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
            source = normalize_media_source(
                user_input[CONF_MEDIA_SOURCE]
            )

            return self.async_create_entry(
                title=NAME,
                data={
                    CONF_MEDIA_SOURCE: source,
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
        """Show the management menu."""

        menu_options = ["libraries"]

        if libraries(self.config_entry):
            menu_options.extend(
                [
                    "overflight",
                    "aerial",
                ]
            )

        menu_options.append("advanced")

        return self.async_show_menu(
            step_id="init",
            menu_options=menu_options,
        )

    async def async_step_libraries(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Show library management."""

        menu_options = ["save_library"]

        if libraries(self.config_entry):
            menu_options.append("remove_library")

        return self.async_show_menu(
            step_id="libraries",
            menu_options=menu_options,
        )

    async def async_step_save_library(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Add or update a named library."""

        schema = vol.Schema(
            {
                vol.Required(ATTR_LIBRARY): selector.TextSelector(
                    selector.TextSelectorConfig()
                ),
                vol.Required(
                    ATTR_MEDIA_SOURCE
                ): _media_selector(),
            }
        )

        if user_input is not None:
            try:
                requested_name = _library_name(
                    user_input[ATTR_LIBRARY]
                )
            except vol.Invalid:
                return self.async_show_form(
                    step_id="save_library",
                    data_schema=schema,
                    errors={
                        ATTR_LIBRARY: "invalid_library_name",
                    },
                )

            source = normalize_media_source(
                user_input[ATTR_MEDIA_SOURCE]
            )

            source_id = source["media_content_id"]
            camera_id = camera_entity_id(source_id)

            if camera_id is not None:
                if self.hass.states.get(camera_id) is None:
                    return self.async_show_form(
                        step_id="save_library",
                        data_schema=schema,
                        errors={
                            ATTR_MEDIA_SOURCE: "source_not_browsable",
                        },
                    )
            else:
                try:
                    await media_source.async_browse_media(
                        self.hass,
                        source_id,
                    )
                except BrowseError:
                    return self.async_show_form(
                        step_id="save_library",
                        data_schema=schema,
                        errors={
                            ATTR_MEDIA_SOURCE: "source_not_browsable",
                        },
                    )

            existing_name = find_library_name(
                self.config_entry,
                requested_name,
            )

            name = existing_name or requested_name

            configured = libraries(self.config_entry)
            configured[name] = source

            options = dict(self.config_entry.options)
            options[CONF_LIBRARIES] = configured

            return self.async_create_entry(
                title="",
                data=options,
            )

        return self.async_show_form(
            step_id="save_library",
            data_schema=schema,
        )

    async def async_step_remove_library(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Remove a named library."""

        names = _library_names(self.config_entry)

        schema = vol.Schema(
            {
                vol.Required(ATTR_LIBRARY): vol.In(names),
            }
        )

        if user_input is not None:
            name = user_input[ATTR_LIBRARY]

            if (
                selected_library(
                    self.config_entry,
                    TARGET_OVERFLIGHT,
                )
                == name
                or selected_library(
                    self.config_entry,
                    TARGET_AERIAL,
                )
                == name
            ):
                return self.async_show_form(
                    step_id="remove_library",
                    data_schema=schema,
                    errors={
                        "base": "library_in_use",
                    },
                )

            configured = libraries(self.config_entry)
            configured.pop(name)

            options = dict(self.config_entry.options)
            options[CONF_LIBRARIES] = configured

            return self.async_create_entry(
                title="",
                data=options,
            )

        return self.async_show_form(
            step_id="remove_library",
            data_schema=schema,
        )

    async def async_step_overflight(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Configure the Overflight feed."""

        names = _library_names(self.config_entry)

        if user_input is not None:
            options = dict(self.config_entry.options)
            options[CONF_OVERFLIGHT_LIBRARY] = user_input[
                CONF_OVERFLIGHT_LIBRARY
            ]

            return self.async_create_entry(
                title="",
                data=options,
            )

        current = selected_library(
            self.config_entry,
            TARGET_OVERFLIGHT,
        )

        return self.async_show_form(
            step_id="overflight",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_OVERFLIGHT_LIBRARY,
                        default=(
                            current
                            if current in names
                            else names[0]
                        ),
                    ): vol.In(names),
                }
            ),
        )

    async def async_step_aerial(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Configure the Aerial Views feed."""

        names = _library_names(self.config_entry)

        if user_input is not None:
            options = dict(self.config_entry.options)
            options[CONF_AERIAL_LIBRARY] = user_input[
                CONF_AERIAL_LIBRARY
            ]

            return self.async_create_entry(
                title="",
                data=options,
            )

        current = selected_library(
            self.config_entry,
            TARGET_AERIAL,
        )

        return self.async_show_form(
            step_id="aerial",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_AERIAL_LIBRARY,
                        default=(
                            current
                            if current in names
                            else names[0]
                        ),
                    ): vol.In(names),
                }
            ),
        )

    async def async_step_advanced(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Configure raw fallback media sources."""

        if user_input is not None:
            options = dict(self.config_entry.options)

            options[CONF_OVERFLIGHT_SOURCE] = normalize_media_source(
                user_input[CONF_OVERFLIGHT_SOURCE]
            )

            options[CONF_AERIAL_SOURCE] = normalize_media_source(
                user_input[CONF_AERIAL_SOURCE]
            )

            return self.async_create_entry(
                title="",
                data=options,
            )

        default_source = default_media_source(
            self.config_entry
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
                vol.Required(
                    CONF_OVERFLIGHT_SOURCE
                ): _media_selector(),
                vol.Required(
                    CONF_AERIAL_SOURCE
                ): _media_selector(),
            }
        )

        return self.async_show_form(
            step_id="advanced",
            data_schema=self.add_suggested_values_to_schema(
                schema,
                {
                    CONF_OVERFLIGHT_SOURCE: overflight_source,
                    CONF_AERIAL_SOURCE: aerial_source,
                },
            ),
        )
