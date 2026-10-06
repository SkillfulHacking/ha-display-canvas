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
    CONF_AERIAL_MIN_RESOLUTION,
    CONF_AERIAL_ORIENTATION,
    CONF_AERIAL_SOURCE,
    CONF_BASE_URL,
    CONF_LIBRARIES,
    CONF_MEDIA_SOURCE,
    CONF_OVERFLIGHT_LIBRARY,
    CONF_OVERFLIGHT_MIN_RESOLUTION,
    CONF_OVERFLIGHT_ORIENTATION,
    CONF_OVERFLIGHT_SOURCE,
    DOMAIN,
    ORIENTATION_ANY,
    ORIENTATION_LANDSCAPE,
    ORIENTATION_PORTRAIT,
    RESOLUTION_1080P,
    RESOLUTION_1440P,
    RESOLUTION_4K,
    RESOLUTION_720P,
    RESOLUTION_ANY,
    NAME,
    TARGET_AERIAL,
    TARGET_OVERFLIGHT,
)
from .feed import feed_url
from .http import async_feed_image_counts
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


ORIENTATION_OPTIONS = {
    ORIENTATION_ANY: "Any",
    ORIENTATION_LANDSCAPE: "Landscape",
    ORIENTATION_PORTRAIT: "Portrait",
}

RESOLUTION_OPTIONS = {
    RESOLUTION_ANY: "Any",
    RESOLUTION_720P: "720p",
    RESOLUTION_1080P: "1080p",
    RESOLUTION_1440P: "1440p",
    RESOLUTION_4K: "4K",
}


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

        menu_options = [
            "general",
            "libraries",
        ]

        if libraries(self.config_entry):
            menu_options.extend(
                [
                    "overflight",
                    "aerial",
                ]
            )

        menu_options.extend(
            [
                "feed_urls",
                "advanced",
            ]
        )

        return self.async_show_menu(
            step_id="init",
            menu_options=menu_options,
        )

    async def async_step_general(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Configure general feed settings."""

        if user_input is not None:
            options = dict(self.config_entry.options)

            base_url = user_input.get(
                CONF_BASE_URL,
                "",
            ).strip().rstrip("/")

            if base_url:
                options[CONF_BASE_URL] = base_url
            else:
                options.pop(CONF_BASE_URL, None)

            return self.async_create_entry(
                title="",
                data=options,
            )

        current = self.config_entry.options.get(
            CONF_BASE_URL,
            "",
        )

        return self.async_show_form(
            step_id="general",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_BASE_URL,
                        default=current,
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.URL,
                        )
                    ),
                }
            ),
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

    async def _async_step_feed(
        self,
        step_id: str,
        target: str,
        library_key: str,
        orientation_key: str,
        resolution_key: str,
        user_input: dict[str, Any] | None,
    ) -> config_entries.ConfigFlowResult:
        """Configure a Display Canvas feed."""

        names = _library_names(self.config_entry)

        if not names:
            return await self.async_step_init()

        if user_input is not None:
            options = dict(self.config_entry.options)

            options[library_key] = user_input[library_key]
            options[orientation_key] = user_input[orientation_key]
            options[resolution_key] = user_input[resolution_key]

            return self.async_create_entry(
                title="",
                data=options,
            )

        current_library = selected_library(
            self.config_entry,
            target,
        )

        current_orientation = self.config_entry.options.get(
            orientation_key,
            ORIENTATION_ANY,
        )

        current_resolution = self.config_entry.options.get(
            resolution_key,
            RESOLUTION_ANY,
        )

        orientation_selector = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    selector.SelectOptionDict(
                        value=value,
                        label=label,
                    )
                    for value, label in ORIENTATION_OPTIONS.items()
                ]
            )
        )

        resolution_selector = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    selector.SelectOptionDict(
                        value=value,
                        label=label,
                    )
                    for value, label in RESOLUTION_OPTIONS.items()
                ]
            )
        )

        published_count, total_count = (
            await async_feed_image_counts(
                self.hass,
                self.config_entry,
                target,
            )
        )

        return self.async_show_form(
            step_id=step_id,
            description_placeholders={
                "published_count": str(published_count),
                "total_count": str(total_count),
            },
            data_schema=vol.Schema(
                {
                    vol.Required(
                        library_key,
                        default=(
                            current_library
                            if current_library in names
                            else names[0]
                        ),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=names,
                        )
                    ),
                    vol.Required(
                        orientation_key,
                        default=current_orientation,
                    ): orientation_selector,
                    vol.Required(
                        resolution_key,
                        default=current_resolution,
                    ): resolution_selector,
                }
            ),
        )

    async def async_step_overflight(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Configure the Overflight feed."""

        return await self._async_step_feed(
            "overflight",
            TARGET_OVERFLIGHT,
            CONF_OVERFLIGHT_LIBRARY,
            CONF_OVERFLIGHT_ORIENTATION,
            CONF_OVERFLIGHT_MIN_RESOLUTION,
            user_input,
        )

    async def async_step_aerial(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Configure the Aerial Views feed."""

        return await self._async_step_feed(
            "aerial",
            TARGET_AERIAL,
            CONF_AERIAL_LIBRARY,
            CONF_AERIAL_ORIENTATION,
            CONF_AERIAL_MIN_RESOLUTION,
            user_input,
        )

    async def async_step_feed_urls(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Show published feed URLs."""

        if user_input is not None:
            return self.async_create_entry(
                title="",
                data=dict(self.config_entry.options),
            )

        return self.async_show_form(
            step_id="feed_urls",
            data_schema=vol.Schema({}),
            description_placeholders={
                "overflight_url": feed_url(
                    self.hass,
                    self.config_entry,
                    "overflight.json",
                ),
                "aerial_url": feed_url(
                    self.hass,
                    self.config_entry,
                    "aerial.csv",
                ),
            },
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
