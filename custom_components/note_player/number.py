"""Number entities for Note Player live tempo (BPM) and room reverb."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import get_device_info
from .const import (
    CONF_DEFAULT_BPM,
    CONF_DEFAULT_REVERB,
    DEFAULT_BPM,
    DEFAULT_REVERB,
    DOMAIN,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Note Player BPM and Reverb number entities."""
    async_add_entities(
        [
            NotePlayerBpmNumber(hass, config_entry),
            NotePlayerReverbNumber(hass, config_entry),
        ]
    )


class NotePlayerBpmNumber(RestoreEntity, NumberEntity):
    """Slider controlling default tempo (BPM) for live Browse Media playback."""

    _attr_has_entity_name = True
    _attr_name = "Tempo (BPM)"
    _attr_icon = "mdi:metronome"
    _attr_native_min_value = 30.0
    _attr_native_max_value = 300.0
    _attr_native_step = 1.0
    _attr_native_unit_of_measurement = "BPM"
    _attr_mode = NumberMode.SLIDER

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the BPM slider entity."""
        self.hass = hass
        self._attr_unique_id = f"{config_entry.entry_id}_live_bpm"
        self._attr_device_info = get_device_info(config_entry.entry_id)
        opts = config_entry.options or config_entry.data
        self._attr_native_value = float(
            hass.data[DOMAIN].get("live_bpm") or opts.get(CONF_DEFAULT_BPM) or DEFAULT_BPM
        )

    async def async_added_to_hass(self) -> None:
        """Restore the last BPM value on startup."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None:
            try:
                val = max(30, min(300, int(float(last_state.state))))
                self._attr_native_value = float(val)
                self.hass.data[DOMAIN]["live_bpm"] = val
            except (TypeError, ValueError):
                pass

    async def async_set_native_value(self, value: float) -> None:
        """Update live BPM value."""
        bpm = max(30, min(300, int(round(value))))
        self._attr_native_value = float(bpm)
        self.hass.data[DOMAIN]["live_bpm"] = bpm
        self.async_write_ha_state()


class NotePlayerReverbNumber(RestoreEntity, NumberEntity):
    """Slider controlling natural stereo room reverb (0.0 to 1.0)."""

    _attr_has_entity_name = True
    _attr_name = "Raumhall (Reverb)"
    _attr_icon = "mdi:waves"
    _attr_native_min_value = 0.0
    _attr_native_max_value = 1.0
    _attr_native_step = 0.05
    _attr_mode = NumberMode.SLIDER

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the reverb slider entity."""
        self.hass = hass
        self._attr_unique_id = f"{config_entry.entry_id}_live_reverb"
        self._attr_device_info = get_device_info(config_entry.entry_id)
        opts = config_entry.options or config_entry.data
        stored = hass.data[DOMAIN].get("live_reverb")
        self._attr_native_value = float(
            stored if stored is not None else opts.get(CONF_DEFAULT_REVERB, DEFAULT_REVERB)
        )

    async def async_added_to_hass(self) -> None:
        """Restore the last reverb value on startup."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None:
            try:
                val = max(0.0, min(1.0, round(float(last_state.state), 2)))
                self._attr_native_value = val
                self.hass.data[DOMAIN]["live_reverb"] = val
            except (TypeError, ValueError):
                pass

    async def async_set_native_value(self, value: float) -> None:
        """Update live reverb amount."""
        reverb = max(0.0, min(1.0, round(float(value), 2)))
        self._attr_native_value = reverb
        self.hass.data[DOMAIN]["live_reverb"] = reverb
        self.async_write_ha_state()
