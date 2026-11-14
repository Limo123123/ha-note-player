"""Home Assistant integration for synthesizing musical notes and instruments."""

from __future__ import annotations

from collections import OrderedDict
import hashlib
import logging
from pathlib import Path
from typing import Any

from aiohttp import web
import voluptuous as vol

from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify

from .const import (
    API_AUDIO_BASE_PATH,
    CONF_DEFAULT_ANNOUNCE,
    CONF_DEFAULT_BPM,
    CONF_DEFAULT_INSTRUMENT,
    CONF_DEFAULT_MEDIA_PLAYER,
    CONF_DEFAULT_REVERB,
    DEFAULT_ANNOUNCE,
    DEFAULT_BPM,
    DEFAULT_INSTRUMENT,
    DEFAULT_LIVE_NOTES,
    DEFAULT_OCTAVE,
    DEFAULT_REVERB,
    DOMAIN,
    INSTRUMENT_IDS,
    MAX_AUDIO_CACHE_ITEMS,
    PRESET_IDS,
    PRESETS,
    STORAGE_KEY,
    STORAGE_VERSION,
    VERSION,
)
from .synth import parse_notes, synthesize_notes

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.TTS,
    Platform.TEXT,
    Platform.SELECT,
    Platform.NUMBER,
]

SERVICE_PLAY_NOTES = "play_notes"
SERVICE_PLAY_PRESET = "play_preset"
SERVICE_SAVE_MELODY = "save_melody"
SERVICE_DELETE_MELODY = "delete_melody"

ATTR_NOTES = "notes"
ATTR_INSTRUMENT = "instrument"
ATTR_BPM = "bpm"
ATTR_OCTAVE = "octave"
ATTR_REVERB = "reverb"
ATTR_VOLUME_LEVEL = "volume_level"
ATTR_ANNOUNCE = "announce"
ATTR_PRESET = "preset"
ATTR_TITLE = "title"
ATTR_MELODY_ID = "melody_id"

EVENT_PLAYED = f"{DOMAIN}_played"

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_BASE_TARGET_FIELDS = {
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Optional("device_id"): cv.ensure_list,
    vol.Optional("area_id"): cv.ensure_list,
    vol.Optional("floor_id"): cv.ensure_list,
    vol.Optional("label_id"): cv.ensure_list,
}

PLAY_NOTES_SCHEMA = vol.Schema(
    {
        **_BASE_TARGET_FIELDS,
        vol.Required(ATTR_NOTES): cv.string,
        vol.Optional(ATTR_INSTRUMENT): vol.In(INSTRUMENT_IDS),
        vol.Optional(ATTR_BPM): vol.All(vol.Coerce(int), vol.Range(min=30, max=300)),
        vol.Optional(ATTR_OCTAVE, default=DEFAULT_OCTAVE): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=7)
        ),
        vol.Optional(ATTR_REVERB): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
        vol.Optional(ATTR_VOLUME_LEVEL): vol.All(
            vol.Coerce(float), vol.Range(min=0.0, max=1.0)
        ),
        vol.Optional(ATTR_ANNOUNCE): cv.boolean,
    }
)

PLAY_PRESET_SCHEMA = vol.Schema(
    {
        **_BASE_TARGET_FIELDS,
        vol.Required(ATTR_PRESET): vol.In(PRESET_IDS),
        vol.Optional(ATTR_INSTRUMENT): vol.In(INSTRUMENT_IDS),
        vol.Optional(ATTR_BPM): vol.All(vol.Coerce(int), vol.Range(min=30, max=300)),
        vol.Optional(ATTR_REVERB): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
        vol.Optional(ATTR_VOLUME_LEVEL): vol.All(
            vol.Coerce(float), vol.Range(min=0.0, max=1.0)
        ),
        vol.Optional(ATTR_ANNOUNCE): cv.boolean,
    }
)

SAVE_MELODY_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_TITLE): cv.string,
        vol.Required(ATTR_NOTES): cv.string,
        vol.Optional(ATTR_INSTRUMENT): vol.In(INSTRUMENT_IDS),
        vol.Optional(ATTR_BPM): vol.All(vol.Coerce(int), vol.Range(min=30, max=300)),
    }
)

DELETE_MELODY_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_MELODY_ID): cv.string,
        vol.Optional(ATTR_TITLE): cv.string,
    }
)


def get_device_info(entry_id: str) -> DeviceInfo:
    """Return shared DeviceInfo for all Note Player entities."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry_id)},
        name="Note Player",
        manufacturer="Note Player",
        model="Instrument Synthesizer",
        sw_version=VERSION,
    )


class NotePlayerAudioView(HomeAssistantView):
    """HTTP endpoint serving synthesized WAV audio to media players on the LAN."""

    url = f"{API_AUDIO_BASE_PATH}/{{filename}}"
    name = "api:note_player:audio"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass

    def _get_audio(self, filename: str) -> bytes | None:
        cache: OrderedDict[str, bytes] = self._hass.data[DOMAIN]["audio_cache"]
        data = cache.get(filename)
        if data is not None:
            cache.move_to_end(filename)
        return data

    async def head(self, request: web.Request, filename: str) -> web.Response:
        """Handle HEAD requests sent by Cast / DLNA / Sonos players before streaming."""
        data = self._get_audio(filename)
        if data is None:
            return web.Response(status=404)
        return web.Response(
            status=200,
            headers={
                "Content-Type": "audio/wav",
                "Content-Length": str(len(data)),
                "Accept-Ranges": "bytes",
                "Cache-Control": "no-store",
            },
        )

    async def get(self, request: web.Request, filename: str) -> web.Response:
        """Serve full or byte-range WAV audio bytes."""
        data = self._get_audio(filename)
        if data is None:
            return web.Response(status=404, text="Audio clip expired or not found")

        total_len = len(data)
        range_header = request.headers.get("Range")
        if range_header and range_header.startswith("bytes="):
            start_s, _, end_s = range_header[6:].partition("-")
            start = int(start_s) if start_s else 0
            end = int(end_s) if end_s else total_len - 1
            start = max(0, min(start, total_len - 1))
            end = max(start, min(end, total_len - 1))
            chunk = data[start : end + 1]
            return web.Response(
                body=chunk,
                status=206,
                headers={
                    "Content-Type": "audio/wav",
                    "Content-Length": str(len(chunk)),
                    "Content-Range": f"bytes {start}-{end}/{total_len}",
                    "Accept-Ranges": "bytes",
                    "Cache-Control": "no-store",
                },
            )

        return web.Response(
            body=data,
            status=200,
            content_type="audio/wav",
            headers={
                "Content-Length": str(total_len),
                "Accept-Ranges": "bytes",
                "Cache-Control": "no-store",
            },
        )


def _store_audio_cache(hass: HomeAssistant, filename: str, wav_bytes: bytes) -> None:
    """Store synthesized WAV bytes in the bounded in-memory LRU cache."""
    cache: OrderedDict[str, bytes] = hass.data[DOMAIN]["audio_cache"]
    cache[filename] = wav_bytes
    cache.move_to_end(filename)
    while len(cache) > MAX_AUDIO_CACHE_ITEMS:
        cache.popitem(last=False)


def _write_audio_backup(www_dir: Path, filename: str, wav_bytes: bytes) -> None:
    """Write a bounded WAV backup copy under /config/www/note_player."""
    try:
        www_dir.mkdir(parents=True, exist_ok=True)
        (www_dir / filename).write_bytes(wav_bytes)
        files = sorted(www_dir.glob("*.wav"), key=lambda p: p.stat().st_mtime)
        for old_file in files[:-MAX_AUDIO_CACHE_ITEMS]:
            old_file.unlink(missing_ok=True)
    except OSError as err:
        _LOGGER.debug("Could not write backup WAV to %s: %s", www_dir, err)


async def async_render_and_cache_wav(
    hass: HomeAssistant,
    *,
    notes: str,
    instrument: str,
    bpm: int,
    octave: int = DEFAULT_OCTAVE,
    reverb: float = DEFAULT_REVERB,
) -> tuple[str, float]:
    """Synthesize notes off the event loop, cache WAV audio, and return (filename, duration_s)."""
    _ensure_initialized(hass)
    try:
        wav_bytes, duration_s = await hass.async_add_executor_job(
            synthesize_notes, notes, instrument, bpm, octave, reverb
        )
    except ValueError as err:
        raise HomeAssistantError(str(err)) from err

    clip_hash = hashlib.sha256(
        f"{instrument}:{bpm}:{octave}:{reverb:.2f}:{notes}".encode()
    ).hexdigest()[:12]
    filename = f"note_player_{instrument}_{clip_hash}.wav"

    _store_audio_cache(hass, filename, wav_bytes)
    www_dir = Path(hass.config.path("www", DOMAIN))
    await hass.async_add_executor_job(_write_audio_backup, www_dir, filename, wav_bytes)
    return filename, duration_s


def _get_base_url(hass: HomeAssistant) -> str:
    """Resolve an internal LAN URL reachable by smart speakers."""
    for kwargs in (
        {"prefer_external": False, "allow_internal": True, "allow_ip": True},
        {"allow_internal": True, "allow_ip": True},
        {},
    ):
        try:
            return get_url(hass, **kwargs).rstrip("/")
        except NoURLAvailableError:
            continue
    raise HomeAssistantError(
        "Keine erreichbare Home-Assistant-URL gefunden. Bitte interne URL unter Einstellungen -> System -> Netzwerk prüfen."
    )


async def _resolve_target_entities(
    hass: HomeAssistant,
    call: ServiceCall,
    default_player: str | None,
) -> list[str]:
    """Resolve target media_player entity IDs from explicit targets, areas, or defaults."""
    explicit = list(call.data.get(ATTR_ENTITY_ID) or [])

    has_indirect_target = any(
        call.data.get(key) for key in ("device_id", "area_id", "floor_id", "label_id")
    )
    if has_indirect_target:
        try:
            from homeassistant.helpers import target as ha_target

            selected = ha_target.async_extract_referenced_entity_ids(
                hass, ha_target.TargetSelection(call.data)
            )
            for eid in selected.referenced | selected.indirectly_referenced:
                if eid.startswith("media_player.") and eid not in explicit:
                    explicit.append(eid)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Could not expand area/device targets: %s", err)

    if explicit:
        return explicit
    if default_player:
        return [default_player]

    raise HomeAssistantError(
        "Kein Media Player ausgewählt (weder im Service-Aufruf noch als Standard-Lautsprecher in den Optionen)."
    )


async def _play_rendered_audio(
    hass: HomeAssistant,
    call: ServiceCall,
    *,
    notes: str,
    instrument: str,
    bpm: int,
    octave: int,
    reverb: float,
    volume_level: float | None,
    announce: bool,
) -> dict[str, Any]:
    """Synthesize notes, cache WAV, and stream to target speakers."""
    domain_data = hass.data[DOMAIN]
    options: dict[str, Any] = domain_data.get("options", {})
    default_player = options.get(CONF_DEFAULT_MEDIA_PLAYER)

    entity_ids = await _resolve_target_entities(hass, call, default_player)
    filename, duration_s = await async_render_and_cache_wav(
        hass,
        notes=notes,
        instrument=instrument,
        bpm=bpm,
        octave=octave,
        reverb=reverb,
    )

    base_url = _get_base_url(hass)
    audio_url = f"{base_url}{API_AUDIO_BASE_PATH}/{filename}"

    if volume_level is not None:
        await hass.services.async_call(
            "media_player",
            "volume_set",
            {ATTR_ENTITY_ID: entity_ids, "volume_level": volume_level},
            blocking=True,
        )

    play_data: dict[str, Any] = {
        ATTR_ENTITY_ID: entity_ids,
        "media_content_id": audio_url,
        "media_content_type": "audio/wav",
    }
    if announce:
        play_data["announce"] = True

    try:
        await hass.services.async_call("media_player", "play_media", play_data, blocking=True)
    except Exception as err:  # noqa: BLE001
        if announce:
            _LOGGER.debug("play_media with announce=True failed (%s); retrying without announce", err)
            play_data.pop("announce", None)
            await hass.services.async_call("media_player", "play_media", play_data, blocking=True)
        else:
            raise

    payload = {
        "entity_id": entity_ids,
        "instrument": instrument,
        "bpm": bpm,
        "duration_s": duration_s,
        "url": audio_url,
    }
    hass.bus.async_fire(EVENT_PLAYED, payload)
    return payload


async def async_ensure_melodies_loaded(hass: HomeAssistant) -> dict[str, dict[str, Any]]:
    """Load saved custom melodies from Home Assistant storage once."""
    _ensure_initialized(hass)
    domain_data = hass.data[DOMAIN]
    if not domain_data["custom_melodies_loaded"]:
        store: Store = domain_data["store"]
        loaded = await store.async_load()
        if isinstance(loaded, dict):
            domain_data["custom_melodies"] = {
                str(k): dict(v) for k, v in loaded.items() if isinstance(v, dict)
            }
        domain_data["custom_melodies_loaded"] = True
    return domain_data["custom_melodies"]


def _register_services(hass: HomeAssistant) -> None:
    """Register Note Player services if not already registered."""

    async def handle_play_notes(call: ServiceCall) -> dict[str, Any]:
        domain_data = hass.data[DOMAIN]
        opts: dict[str, Any] = domain_data.get("options", {})
        return await _play_rendered_audio(
            hass,
            call,
            notes=call.data[ATTR_NOTES],
            instrument=call.data.get(
                ATTR_INSTRUMENT,
                domain_data.get("live_instrument")
                or opts.get(CONF_DEFAULT_INSTRUMENT, DEFAULT_INSTRUMENT),
            ),
            bpm=call.data.get(
                ATTR_BPM,
                domain_data.get("live_bpm") or opts.get(CONF_DEFAULT_BPM, DEFAULT_BPM),
            ),
            octave=call.data.get(ATTR_OCTAVE, DEFAULT_OCTAVE),
            reverb=call.data.get(
                ATTR_REVERB,
                domain_data.get("live_reverb")
                if domain_data.get("live_reverb") is not None
                else opts.get(CONF_DEFAULT_REVERB, DEFAULT_REVERB),
            ),
            volume_level=call.data.get(ATTR_VOLUME_LEVEL),
            announce=call.data.get(
                ATTR_ANNOUNCE, opts.get(CONF_DEFAULT_ANNOUNCE, DEFAULT_ANNOUNCE)
            ),
        )

    async def handle_play_preset(call: ServiceCall) -> dict[str, Any]:
        domain_data = hass.data[DOMAIN]
        opts: dict[str, Any] = domain_data.get("options", {})
        preset_key = call.data[ATTR_PRESET]
        preset = PRESETS[preset_key]
        return await _play_rendered_audio(
            hass,
            call,
            notes=str(preset["notes"]),
            instrument=call.data.get(ATTR_INSTRUMENT, str(preset["instrument"])),
            bpm=call.data.get(ATTR_BPM, int(preset["bpm"])),
            octave=DEFAULT_OCTAVE,
            reverb=call.data.get(
                ATTR_REVERB,
                domain_data.get("live_reverb")
                if domain_data.get("live_reverb") is not None
                else opts.get(CONF_DEFAULT_REVERB, DEFAULT_REVERB),
            ),
            volume_level=call.data.get(ATTR_VOLUME_LEVEL),
            announce=call.data.get(
                ATTR_ANNOUNCE, opts.get(CONF_DEFAULT_ANNOUNCE, DEFAULT_ANNOUNCE)
            ),
        )

    async def handle_save_melody(call: ServiceCall) -> dict[str, Any]:
        custom_melodies = await async_ensure_melodies_loaded(hass)
        domain_data = hass.data[DOMAIN]
        opts: dict[str, Any] = domain_data.get("options", {})

        title = call.data[ATTR_TITLE].strip()
        notes = call.data[ATTR_NOTES].strip()
        if not title:
            raise HomeAssistantError("Bitte einen Titel für die Melodie angeben.")

        fallback_bpm = int(
            domain_data.get("live_bpm") or opts.get(CONF_DEFAULT_BPM, DEFAULT_BPM)
        )
        try:
            events, parsed_bpm = parse_notes(notes, bpm=fallback_bpm)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
        if not events:
            raise HomeAssistantError("Keine gültigen Noten zum Speichern gefunden.")

        instrument = call.data.get(
            ATTR_INSTRUMENT,
            domain_data.get("live_instrument")
            or opts.get(CONF_DEFAULT_INSTRUMENT, DEFAULT_INSTRUMENT),
        )
        bpm = int(call.data.get(ATTR_BPM, parsed_bpm))

        melody_id = slugify(title) or hashlib.sha1(title.encode()).hexdigest()[:8]
        entry = {
            "id": melody_id,
            "title": title,
            "notes": notes,
            "instrument": instrument,
            "bpm": bpm,
        }
        custom_melodies[melody_id] = entry
        await domain_data["store"].async_save(custom_melodies)
        return entry

    async def handle_delete_melody(call: ServiceCall) -> None:
        custom_melodies = await async_ensure_melodies_loaded(hass)
        domain_data = hass.data[DOMAIN]
        melody_id = (call.data.get(ATTR_MELODY_ID) or "").strip()
        title = (call.data.get(ATTR_TITLE) or "").strip()

        target_id: str | None = None
        if melody_id and melody_id in custom_melodies:
            target_id = melody_id
        elif title:
            title_l = title.lower()
            for k, v in custom_melodies.items():
                if str(v.get("title", "")).lower() == title_l or k == slugify(title):
                    target_id = k
                    break

        if target_id is None:
            raise HomeAssistantError(
                "Gespeicherte Melodie nicht gefunden (melody_id oder passenden title angeben)."
            )

        custom_melodies.pop(target_id, None)
        await domain_data["store"].async_save(custom_melodies)

    if not hass.services.has_service(DOMAIN, SERVICE_PLAY_NOTES):
        hass.services.async_register(
            DOMAIN,
            SERVICE_PLAY_NOTES,
            handle_play_notes,
            schema=PLAY_NOTES_SCHEMA,
            supports_response=SupportsResponse.OPTIONAL,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_PLAY_PRESET):
        hass.services.async_register(
            DOMAIN,
            SERVICE_PLAY_PRESET,
            handle_play_preset,
            schema=PLAY_PRESET_SCHEMA,
            supports_response=SupportsResponse.OPTIONAL,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_SAVE_MELODY):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SAVE_MELODY,
            handle_save_melody,
            schema=SAVE_MELODY_SCHEMA,
            supports_response=SupportsResponse.OPTIONAL,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_DELETE_MELODY):
        hass.services.async_register(
            DOMAIN,
            SERVICE_DELETE_MELODY,
            handle_delete_melody,
            schema=DELETE_MELODY_SCHEMA,
        )


def _ensure_initialized(hass: HomeAssistant) -> None:
    """Initialize shared storage and register the HTTP audio view once."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {
            "audio_cache": OrderedDict(),
            "options": {},
            "view_registered": False,
            "store": Store(hass, STORAGE_VERSION, STORAGE_KEY),
            "custom_melodies": {},
            "custom_melodies_loaded": False,
            "live_notes": DEFAULT_LIVE_NOTES,
            "live_instrument": DEFAULT_INSTRUMENT,
            "live_bpm": DEFAULT_BPM,
            "live_reverb": DEFAULT_REVERB,
        }
    if getattr(hass, "http", None) is not None and not hass.data[DOMAIN]["view_registered"]:
        hass.http.register_view(NotePlayerAudioView(hass))
        hass.data[DOMAIN]["view_registered"] = True
    _register_services(hass)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Note Player domain components."""
    _ensure_initialized(hass)
    await async_ensure_melodies_loaded(hass)
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update cached default options when the user changes integration options."""
    if DOMAIN in hass.data:
        opts = dict(entry.options or entry.data)
        hass.data[DOMAIN]["options"] = opts


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Note Player from a config entry."""
    _ensure_initialized(hass)
    await async_ensure_melodies_loaded(hass)
    opts = dict(entry.options or entry.data)
    domain_data = hass.data[DOMAIN]
    domain_data["options"] = opts
    if opts.get(CONF_DEFAULT_INSTRUMENT) in INSTRUMENT_IDS:
        domain_data["live_instrument"] = opts[CONF_DEFAULT_INSTRUMENT]
    if opts.get(CONF_DEFAULT_BPM) is not None:
        domain_data["live_bpm"] = int(opts[CONF_DEFAULT_BPM])
    if opts.get(CONF_DEFAULT_REVERB) is not None:
        domain_data["live_reverb"] = float(opts[CONF_DEFAULT_REVERB])

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Note Player config entry, platforms, and services."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    if DOMAIN in hass.data:
        hass.data[DOMAIN]["options"] = {}
    for service in (
        SERVICE_PLAY_NOTES,
        SERVICE_PLAY_PRESET,
        SERVICE_SAVE_MELODY,
        SERVICE_DELETE_MELODY,
    ):
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)
    return True
