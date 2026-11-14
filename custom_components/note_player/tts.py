"""Text-to-Speech entity for Note Player — enables live note input & instrument dropdown inside Browse Media."""

from __future__ import annotations

import re
from typing import Any

from homeassistant.components import tts
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import get_device_info
from .const import (
    DEFAULT_BPM,
    DEFAULT_INSTRUMENT,
    DEFAULT_OCTAVE,
    DEFAULT_REVERB,
    DOMAIN,
    INSTRUMENTS,
    PRESETS,
)
from .synth import synthesize_notes

_OPTION_TOKEN_RE = re.compile(r"^(bpm|reverb|inst|instrument|preset)=([^\s]+)$", re.IGNORECASE)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Note Player TTS entity."""
    async_add_entities([NotePlayerTTSEntity(hass, config_entry)])


def _parse_tts_message(
    message: str,
    default_instrument: str,
    default_bpm: int,
    default_reverb: float,
) -> tuple[str, str, int, float]:
    """Parse optional inline parameters like 'bpm=140 inst=guitar C4:4 E4:4 G4:2'."""
    instrument = default_instrument
    bpm = default_bpm
    reverb = default_reverb
    explicit_inst = False
    explicit_bpm = False
    preset_notes: str | None = None

    remaining_tokens = message.strip().split()
    idx = 0
    while idx < len(remaining_tokens):
        match = _OPTION_TOKEN_RE.match(remaining_tokens[idx])
        if not match:
            break
        key = match.group(1).lower()
        val = match.group(2)

        if key == "bpm":
            try:
                bpm = max(30, min(300, int(val)))
                explicit_bpm = True
            except ValueError:
                pass
        elif key == "reverb":
            try:
                reverb = max(0.0, min(1.0, float(val)))
            except ValueError:
                pass
        elif key in ("inst", "instrument"):
            val_l = val.lower()
            if val_l in INSTRUMENTS:
                instrument = val_l
                explicit_inst = True
        elif key == "preset":
            pdata = PRESETS.get(val.lower())
            if pdata:
                preset_notes = str(pdata["notes"])
                if not explicit_bpm:
                    bpm = int(pdata["bpm"])
                if not explicit_inst and default_instrument == DEFAULT_INSTRUMENT:
                    instrument = str(pdata["instrument"])
        idx += 1

    notes = " ".join(remaining_tokens[idx:]).strip()
    if not notes and preset_notes:
        notes = preset_notes

    return notes, instrument, bpm, reverb


class NotePlayerTTSEntity(tts.TextToSpeechEntity):
    """TTS-style Note Player entity so users can enter notes and pick an instrument in Browse Media."""

    _attr_name = "Note Player (Noten-Eingabe)"
    _attr_supported_languages = ["de", "de-DE", "en", "en-US"]
    _attr_default_language = "de"
    _attr_supported_options = [tts.ATTR_VOICE]
    _attr_default_options = {tts.ATTR_VOICE: DEFAULT_INSTRUMENT}
    _attr_icon = "mdi:music-note-plus"

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the Note Player TTS entity."""
        self.hass = hass
        self._attr_unique_id = f"{config_entry.entry_id}_tts"
        self._attr_device_info = get_device_info(config_entry.entry_id)

    @callback
    def async_get_supported_voices(self, language: str) -> list[tts.Voice] | None:
        """Expose all 13 synthesized instruments in the Browse Media Voice dropdown."""
        name_key = "name_en" if language.lower().startswith("en") else "name_de"
        return [tts.Voice(inst_id, info[name_key]) for inst_id, info in INSTRUMENTS.items()]

    async def async_get_tts_audio(
        self,
        message: str,
        language: str,
        options: dict[str, Any],
    ) -> tts.TtsAudioType:
        """Synthesize musical notes entered via the Browse Media TTS box into WAV audio."""
        domain_data: dict[str, Any] = self.hass.data.get(DOMAIN, {})
        entry_opts: dict[str, Any] = domain_data.get("options", {})

        voice_inst = options.get(tts.ATTR_VOICE)
        fallback_inst = str(
            voice_inst
            or domain_data.get("live_instrument")
            or entry_opts.get("default_instrument")
            or DEFAULT_INSTRUMENT
        )
        if fallback_inst not in INSTRUMENTS:
            fallback_inst = DEFAULT_INSTRUMENT

        fallback_bpm = int(
            domain_data.get("live_bpm")
            or entry_opts.get("default_bpm")
            or DEFAULT_BPM
        )
        fallback_reverb = float(
            domain_data.get("live_reverb")
            if domain_data.get("live_reverb") is not None
            else entry_opts.get("default_reverb", DEFAULT_REVERB)
        )

        notes, instrument, bpm, reverb = _parse_tts_message(
            message, fallback_inst, fallback_bpm, fallback_reverb
        )
        if not notes:
            raise HomeAssistantError(
                "Bitte Noten eingeben (z. B. 'A4:4 D4:2 F4:4' oder 'C4+E4+G4:2 Am:2 G7:2 Cmaj:1')."
            )

        try:
            wav_bytes, _duration_s = await self.hass.async_add_executor_job(
                synthesize_notes, notes, instrument, bpm, DEFAULT_OCTAVE, reverb
            )
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err

        return ("wav", wav_bytes)
