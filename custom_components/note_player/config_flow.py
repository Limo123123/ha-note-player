"""Config flow and options flow for Note Player."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_DEFAULT_ANNOUNCE,
    CONF_DEFAULT_BPM,
    CONF_DEFAULT_INSTRUMENT,
    CONF_DEFAULT_MEDIA_PLAYER,
    CONF_DEFAULT_REVERB,
    DEFAULT_ANNOUNCE,
    DEFAULT_BPM,
    DEFAULT_INSTRUMENT,
    DEFAULT_REVERB,
    DOMAIN,
    INSTRUMENTS,
)


def _build_settings_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Build shared schema for initial setup and options reconfiguration."""
    instrument_options = [
        SelectOptionDict(value=key, label=info["name_de"])
        for key, info in INSTRUMENTS.items()
    ]

    default_player = defaults.get(CONF_DEFAULT_MEDIA_PLAYER)
    schema_dict: dict[Any, Any] = {}

    if default_player:
        schema_dict[vol.Optional(CONF_DEFAULT_MEDIA_PLAYER, default=default_player)] = EntitySelector(
            EntitySelectorConfig(domain="media_player")
        )
    else:
        schema_dict[vol.Optional(CONF_DEFAULT_MEDIA_PLAYER)] = EntitySelector(
            EntitySelectorConfig(domain="media_player")
        )

    schema_dict[
        vol.Required(
            CONF_DEFAULT_INSTRUMENT,
            default=defaults.get(CONF_DEFAULT_INSTRUMENT, DEFAULT_INSTRUMENT),
        )
    ] = SelectSelector(
        SelectSelectorConfig(
            options=instrument_options,
            mode=SelectSelectorMode.DROPDOWN,
        )
    )
    schema_dict[
        vol.Required(CONF_DEFAULT_BPM, default=defaults.get(CONF_DEFAULT_BPM, DEFAULT_BPM))
    ] = NumberSelector(
        NumberSelectorConfig(min=40, max=240, step=1, mode=NumberSelectorMode.SLIDER)
    )
    schema_dict[
        vol.Required(
            CONF_DEFAULT_REVERB, default=defaults.get(CONF_DEFAULT_REVERB, DEFAULT_REVERB)
        )
    ] = NumberSelector(
        NumberSelectorConfig(min=0.0, max=1.0, step=0.05, mode=NumberSelectorMode.SLIDER)
    )
    schema_dict[
        vol.Required(
            CONF_DEFAULT_ANNOUNCE,
            default=defaults.get(CONF_DEFAULT_ANNOUNCE, DEFAULT_ANNOUNCE),
        )
    ] = BooleanSelector()

    return vol.Schema(schema_dict)


class NotePlayerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle initial setup config flow for Note Player."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the user setup step."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(
                title="Note Player (Instrument Synthesizer)",
                data={},
                options=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=_build_settings_schema({}),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow handler."""
        return NotePlayerOptionsFlow()


class NotePlayerOptionsFlow(OptionsFlow):
    """Handle options flow to adjust default speaker, instrument, BPM, and reverb."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage Note Player default options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = dict(self.config_entry.options or self.config_entry.data)
        return self.async_show_form(
            step_id="init",
            data_schema=_build_settings_schema(current),
        )
