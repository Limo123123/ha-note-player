"""Select entity for choosing the active Note Player instrument."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import get_device_info
from .const import (
    CONF_DEFAULT_INSTRUMENT,
    DEFAULT_INSTRUMENT,
    DOMAIN,
    INSTRUMENT_IDS,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Note Player instrument selector entity."""
    async_add_entities([NotePlayerInstrumentSelect(hass, config_entry)])


class NotePlayerInstrumentSelect(RestoreEntity, SelectEntity):
    """Select entity controlling the default instrument for live Browse Media playback."""

    _attr_has_entity_name = True
    _attr_name = "Instrument"
    _attr_translation_key = "instrument"
    _attr_icon = "mdi:guitar-acoustic"
    _attr_options = INSTRUMENT_IDS

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the instrument selector."""
        self.hass = hass
        self._attr_unique_id = f"{config_entry.entry_id}_live_instrument"
        self._attr_device_info = get_device_info(config_entry.entry_id)
        opts = config_entry.options or config_entry.data
        current = str(
            hass.data[DOMAIN].get("live_instrument")
            or opts.get(CONF_DEFAULT_INSTRUMENT)
            or DEFAULT_INSTRUMENT
        )
        if current not in INSTRUMENT_IDS:
            current = DEFAULT_INSTRUMENT
        self._attr_current_option = current

    async def async_added_to_hass(self) -> None:
        """Restore the last selected instrument on startup."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state in INSTRUMENT_IDS:
            self._attr_current_option = last_state.state
            self.hass.data[DOMAIN]["live_instrument"] = last_state.state

    async def async_select_option(self, option: str) -> None:
        """Select a new active instrument."""
        if option not in INSTRUMENT_IDS:
            raise ValueError(f"Unsupported instrument: {option}")
        self._attr_current_option = option
        self.hass.data[DOMAIN]["live_instrument"] = option
        self.async_write_ha_state()
