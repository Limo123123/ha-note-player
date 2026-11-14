"""Status and render progress sensor for Note Player."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SIGNAL_STATUS_UPDATED, get_device_info
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Note Player status sensor entity."""
    async_add_entities([NotePlayerStatusSensor(hass, config_entry)])


class NotePlayerStatusSensor(SensorEntity):
    """Sensor entity exposing live Note Player synthesis status and render progress."""

    _attr_has_entity_name = True
    _attr_name = "Status"
    _attr_translation_key = "status"
    _attr_icon = "mdi:music-circle-outline"

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the status sensor."""
        self.hass = hass
        self._attr_unique_id = f"{config_entry.entry_id}_status"
        self._attr_device_info = get_device_info(config_entry.entry_id)

    @property
    def native_value(self) -> str:
        """Return the current human-readable status string."""
        status_info: dict[str, Any] = self.hass.data.get(DOMAIN, {}).get("status", {})
        return str(status_info.get("state_text", "Bereit"))

    @property
    def icon(self) -> str:
        """Return a dynamic icon matching the current state."""
        status_info: dict[str, Any] = self.hass.data.get(DOMAIN, {}).get("status", {})
        phase = status_info.get("phase", "idle")
        if phase == "rendering":
            return "mdi:progress-clock"
        if phase == "playing":
            return "mdi:music-note"
        if phase == "error":
            return "mdi:alert-circle-outline"
        return "mdi:check-circle-outline"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return detailed render progress and playback attributes."""
        status_info: dict[str, Any] = self.hass.data.get(DOMAIN, {}).get("status", {})
        return {
            "phase": status_info.get("phase", "idle"),
            "progress_percent": status_info.get("progress_percent", 0),
            "current_item": status_info.get("current_item"),
            "instrument": status_info.get("instrument"),
            "duration_s": status_info.get("duration_s"),
            "cached": status_info.get("cached", False),
            "last_error": status_info.get("last_error"),
        }

    async def async_added_to_hass(self) -> None:
        """Subscribe to status updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_STATUS_UPDATED,
                self._handle_status_update,
            )
        )

    @callback
    def _handle_status_update(self) -> None:
        """Write updated status to Home Assistant state machine."""
        self.async_write_ha_state()
