"""Media Source implementation for Note Player (Home Assistant Browse Media)."""

from __future__ import annotations

from typing import Any
from urllib.parse import unquote

from homeassistant.components.media_player import MediaClass, MediaType
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import async_ensure_melodies_loaded, async_render_and_cache_wav
from .const import (
    API_AUDIO_BASE_PATH,
    DEFAULT_BPM,
    DEFAULT_INSTRUMENT,
    DEFAULT_LIVE_NOTES,
    DEFAULT_OCTAVE,
    DEFAULT_REVERB,
    DOMAIN,
    INSTRUMENTS,
    PAD_ITEMS,
    PRESETS,
    RIFFS,
)


async def async_get_media_source(hass: HomeAssistant) -> NotePlayerMediaSource:
    """Set up Note Player media source."""
    return NotePlayerMediaSource(hass)


class NotePlayerMediaSource(MediaSource):
    """Expose Note Player instruments, presets, riffs, pads, and custom melodies in Browse Media."""

    name = "Note Player (Instrumente & Melodien)"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the Note Player media source."""
        super().__init__(DOMAIN)
        self.hass = hass

    def _get_live_defaults(self) -> tuple[str, str, int, float]:
        """Read current live entity settings with safe fallbacks."""
        domain_data: dict[str, Any] = self.hass.data.get(DOMAIN, {})
        options: dict[str, Any] = domain_data.get("options", {})
        notes = str(domain_data.get("live_notes") or DEFAULT_LIVE_NOTES)
        instrument = str(
            domain_data.get("live_instrument")
            or options.get("default_instrument")
            or DEFAULT_INSTRUMENT
        )
        if instrument not in INSTRUMENTS:
            instrument = DEFAULT_INSTRUMENT
        bpm = int(domain_data.get("live_bpm") or options.get("default_bpm") or DEFAULT_BPM)
        reverb = float(
            domain_data.get("live_reverb")
            if domain_data.get("live_reverb") is not None
            else options.get("default_reverb", DEFAULT_REVERB)
        )
        return notes, instrument, max(30, min(300, bpm)), max(0.0, min(1.0, reverb))

    @staticmethod
    def _folder_node(
        identifier: str | None,
        title: str,
        *,
        children: list[BrowseMediaSource] | None = None,
        children_media_class: MediaClass = MediaClass.MUSIC,
    ) -> BrowseMediaSource:
        """Build a folder node for BrowseMediaSource."""
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=identifier,
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.MUSIC,
            title=title,
            can_play=False,
            can_expand=True,
            children=children or [],
            children_media_class=children_media_class,
        )

    @staticmethod
    def _playable_node(identifier: str, title: str) -> BrowseMediaSource:
        """Build a playable WAV item node for BrowseMediaSource."""
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=identifier,
            media_class=MediaClass.MUSIC,
            media_content_type="audio/wav",
            title=title,
            can_play=True,
            can_expand=False,
        )

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        """Return BrowseMediaSource tree for the requested Note Player folder."""
        custom_melodies = await async_ensure_melodies_loaded(self.hass)
        ident = (item.identifier or "").strip("/")

        if not ident:
            return self._build_root(custom_melodies)

        if ident == "presets_default":
            children = [
                self._playable_node(
                    f"preset_orig/{preset_id}",
                    f"{pdata['title']} ({INSTRUMENTS[str(pdata['instrument'])]['name_de']}, {pdata['bpm']} BPM)",
                )
                for preset_id, pdata in PRESETS.items()
            ]
            return self._folder_node(
                "presets_default",
                "Eingebaute Melodien (Original-Instrument)",
                children=children,
            )

        if ident == "custom_list":
            children = [
                self._playable_node(
                    f"custom_orig/{melody_id}",
                    f"{mdata['title']} ({INSTRUMENTS.get(str(mdata.get('instrument')), {}).get('name_de', mdata.get('instrument'))}, {mdata.get('bpm', DEFAULT_BPM)} BPM)",
                )
                for melody_id, mdata in custom_melodies.items()
            ]
            if not children:
                notes, inst, bpm, _ = self._get_live_defaults()
                inst_label = INSTRUMENTS[inst]["name_de"]
                children.append(
                    self._playable_node(
                        "live/default",
                        f"▶ Aktuelle Noten-Eingabe ({inst_label}, {bpm} BPM): {notes[:40]}",
                    )
                )
            return self._folder_node(
                "custom_list",
                "Eigene gespeicherte Melodien",
                children=children,
            )

        if ident.startswith("inst/"):
            instrument_id = ident.split("/", 1)[1]
            if instrument_id not in INSTRUMENTS:
                raise Unresolvable(f"Unbekanntes Instrument: {instrument_id}")
            return self._build_instrument_folder(instrument_id, custom_melodies)

        if ident.startswith("riffs/"):
            instrument_id = ident.split("/", 1)[1]
            if instrument_id not in INSTRUMENTS:
                raise Unresolvable(f"Unbekanntes Instrument: {instrument_id}")
            inst_name = INSTRUMENTS[instrument_id]["name_de"]
            children = [
                self._playable_node(
                    f"riff/{instrument_id}/{riff_id}",
                    f"{rdata['title']} ({rdata['bpm']} BPM)",
                )
                for riff_id, rdata in RIFFS.items()
            ]
            return self._folder_node(
                ident,
                f"{inst_name} — Akkorde, Riffs & Tonleitern",
                children=children,
            )

        if ident.startswith("pad/"):
            instrument_id = ident.split("/", 1)[1]
            if instrument_id not in INSTRUMENTS:
                raise Unresolvable(f"Unbekanntes Instrument: {instrument_id}")
            inst_name = INSTRUMENTS[instrument_id]["name_de"]
            children = [
                self._playable_node(
                    f"pad_item/{instrument_id}/{pad_id}",
                    f"{pdata['title']} ({pdata['notes']})",
                )
                for pad_id, pdata in PAD_ITEMS.items()
            ]
            return self._folder_node(
                ident,
                f"{inst_name} — Einzelnoten & Akkorde",
                children=children,
            )

        raise Unresolvable(f"Unbekannter Browse-Media-Pfad: {ident}")

    def _build_root(self, custom_melodies: dict[str, dict[str, Any]]) -> BrowseMediaSource:
        """Build the top-level Browse Media folder for Note Player."""
        notes, live_inst, live_bpm, _ = self._get_live_defaults()
        live_inst_name = INSTRUMENTS[live_inst]["name_de"]
        preview = notes if len(notes) <= 36 else f"{notes[:33]}..."

        children: list[BrowseMediaSource] = [
            self._playable_node(
                "live/default",
                f"▶ Aktuelle Noten-Eingabe ({live_inst_name}, {live_bpm} BPM): {preview}",
            ),
            self._folder_node(
                "presets_default",
                "⭐ Eingebaute Melodien (Original-Instrument)",
            ),
            self._folder_node(
                "custom_list",
                f"📚 Eigene gespeicherte Melodien ({len(custom_melodies)})",
            ),
        ]

        for inst_id, info in INSTRUMENTS.items():
            children.append(
                self._folder_node(
                    f"inst/{inst_id}",
                    f"🎵 {info['name_de']}",
                )
            )

        return self._folder_node(
            None,
            "Note Player (Instrumente & Melodien)",
            children=children,
            children_media_class=MediaClass.DIRECTORY,
        )

    def _build_instrument_folder(
        self,
        instrument_id: str,
        custom_melodies: dict[str, dict[str, Any]],
    ) -> BrowseMediaSource:
        """Build the Browse Media folder for a single instrument."""
        inst_name = INSTRUMENTS[instrument_id]["name_de"]
        live_notes, _, live_bpm, _ = self._get_live_defaults()
        preview = live_notes if len(live_notes) <= 32 else f"{live_notes[:29]}..."

        children: list[BrowseMediaSource] = [
            self._playable_node(
                f"live/{instrument_id}",
                f"▶ Aktuelle Noten-Eingabe ({live_bpm} BPM): {preview}",
            ),
            self._folder_node(
                f"pad/{instrument_id}",
                f"🎹 Einzelnoten & Akkorde ({inst_name})",
            ),
            self._folder_node(
                f"riffs/{instrument_id}",
                f"🎼 Riffs, Tonleitern & Kadenzen ({inst_name})",
            ),
        ]

        for melody_id, mdata in custom_melodies.items():
            children.append(
                self._playable_node(
                    f"custom/{instrument_id}/{melody_id}",
                    f"📚 {mdata['title']} ({mdata.get('bpm', DEFAULT_BPM)} BPM)",
                )
            )

        for preset_id, pdata in PRESETS.items():
            children.append(
                self._playable_node(
                    f"preset/{instrument_id}/{preset_id}",
                    f"⭐ {pdata['title']}",
                )
            )

        return self._folder_node(
            f"inst/{instrument_id}",
            inst_name,
            children=children,
        )

    async def _resolve_descriptor(
        self, ident: str
    ) -> tuple[str, str, int, float]:
        """Resolve an identifier into (notes, instrument, bpm, reverb)."""
        custom_melodies = await async_ensure_melodies_loaded(self.hass)
        live_notes, live_inst, live_bpm, live_reverb = self._get_live_defaults()
        parts = ident.split("/")

        kind = parts[0] if parts else ""

        if kind == "live" and len(parts) == 2:
            target_inst = live_inst if parts[1] == "default" else parts[1]
            if target_inst not in INSTRUMENTS:
                raise Unresolvable(f"Unbekanntes Instrument: {target_inst}")
            return live_notes, target_inst, live_bpm, live_reverb

        if kind == "preset_orig" and len(parts) == 2:
            preset = PRESETS.get(parts[1])
            if not preset:
                raise Unresolvable(f"Unbekanntes Preset: {parts[1]}")
            return (
                str(preset["notes"]),
                str(preset["instrument"]),
                int(preset["bpm"]),
                live_reverb,
            )

        if kind == "preset" and len(parts) == 3:
            inst_id, preset_id = parts[1], parts[2]
            preset = PRESETS.get(preset_id)
            if inst_id not in INSTRUMENTS or not preset:
                raise Unresolvable(f"Ungültiges Preset oder Instrument: {ident}")
            return str(preset["notes"]), inst_id, int(preset["bpm"]), live_reverb

        if kind == "custom_orig" and len(parts) == 2:
            melody = custom_melodies.get(parts[1])
            if not melody:
                raise Unresolvable(f"Melodie nicht gefunden: {parts[1]}")
            inst_id = str(melody.get("instrument") or live_inst)
            if inst_id not in INSTRUMENTS:
                inst_id = live_inst
            bpm = int(melody.get("bpm") or live_bpm)
            return str(melody["notes"]), inst_id, bpm, live_reverb

        if kind == "custom" and len(parts) == 3:
            inst_id, melody_id = parts[1], parts[2]
            melody = custom_melodies.get(melody_id)
            if inst_id not in INSTRUMENTS or not melody:
                raise Unresolvable(f"Ungültige Melodie oder Instrument: {ident}")
            return str(melody["notes"]), inst_id, int(melody.get("bpm") or live_bpm), live_reverb

        if kind == "riff" and len(parts) == 3:
            inst_id, riff_id = parts[1], parts[2]
            riff = RIFFS.get(riff_id)
            if inst_id not in INSTRUMENTS or not riff:
                raise Unresolvable(f"Ungültiges Riff oder Instrument: {ident}")
            return str(riff["notes"]), inst_id, int(riff["bpm"]), live_reverb

        if kind == "pad_item" and len(parts) == 3:
            inst_id, pad_id = parts[1], parts[2]
            pad_item = PAD_ITEMS.get(pad_id)
            if inst_id not in INSTRUMENTS or not pad_item:
                raise Unresolvable(f"Ungültiges Pad-Element oder Instrument: {ident}")
            return str(pad_item["notes"]), inst_id, 120, live_reverb

        if kind == "play":
            play_parts = ident.split("/", 3)
            if len(play_parts) != 4:
                raise Unresolvable(f"Ungültige play-URI: {ident}")
            _, inst_id, bpm_raw, notes_raw = play_parts
            if inst_id not in INSTRUMENTS:
                raise Unresolvable(f"Unbekanntes Instrument: {inst_id}")
            try:
                bpm = max(30, min(300, int(bpm_raw)))
            except ValueError as err:
                raise Unresolvable(f"Ungültiges Tempo: {bpm_raw}") from err
            notes = unquote(notes_raw).strip()
            if not notes:
                raise Unresolvable("Keine Noten angegeben")
            return notes, inst_id, bpm, live_reverb

        raise Unresolvable(f"Unbekannte Note-Player Media-ID: {ident}")

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Synthesize the requested media-source item into a cached WAV URL."""
        ident = (item.identifier or "").strip("/")
        notes, instrument, bpm, reverb = await self._resolve_descriptor(ident)

        try:
            filename, _duration_s = await async_render_and_cache_wav(
                self.hass,
                notes=notes,
                instrument=instrument,
                bpm=bpm,
                octave=DEFAULT_OCTAVE,
                reverb=reverb,
            )
        except HomeAssistantError as err:
            raise Unresolvable(str(err)) from err

        return PlayMedia(url=f"{API_AUDIO_BASE_PATH}/{filename}", mime_type="audio/wav")
