"""Text entity for entering live musical notes usable in Browse Media."""

from __future__ import annotations

from homeassistant.components.text import TextEntity, TextMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import get_device_info
from .const import DEFAULT_LIVE_NOTES, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the live notes text entity."""
    async_add_entities([NotePlayerNotesText(hass, config_entry)])


class NotePlayerNotesText(RestoreEntity, TextEntity):
    """Editable note sequence for immediate playback in Browse Media."""

    _attr_has_entity_name = True
    _attr_name = "Noten-Eingabe"
    _attr_icon = "mdi:music-clef-treble"
    _attr_native_min = 1
    _attr_native_max = 255
    _attr_mode = TextMode.TEXT

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the text entity."""
        self.hass = hass
        self._attr_unique_id = f"{config_entry.entry_id}_live_notes"
        self._attr_device_info = get_device_info(config_entry.entry_id)
        initial = str(hass.data[DOMAIN].get("live_notes") or DEFAULT_LIVE_NOTES)
        self._attr_native_value = initial[:255]

    async def async_added_to_hass(self) -> None:
        """Restore previously entered notes after restart."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if (
            last_state is not None
            and last_state.state not in ("unknown", "unavailable", "")
        ):
            val = last_state.state[:255]
            self._attr_native_value = val
            self.hass.data[DOMAIN]["live_notes"] = val

    async def async_set_value(self, value: str) -> None:
        """Update the live notes string stored for Browse Media playback."""
        cleaned = value.strip() or DEFAULT_LIVE_NOTES
        self._attr_native_value = cleaned[:255]
        self.hass.data[DOMAIN]["live_notes"] = self._attr_native_value
        self.async_write_ha_state()
