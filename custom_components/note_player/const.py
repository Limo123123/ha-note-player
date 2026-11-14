"""Constants, instrument definitions, and built-in melody presets for Note Player."""

from __future__ import annotations

DOMAIN = "note_player"
VERSION = "1.0.0"

CONF_DEFAULT_MEDIA_PLAYER = "default_media_player"
CONF_DEFAULT_INSTRUMENT = "default_instrument"
CONF_DEFAULT_BPM = "default_bpm"
CONF_DEFAULT_REVERB = "default_reverb"
CONF_DEFAULT_ANNOUNCE = "default_announce"

DEFAULT_BPM = 120
DEFAULT_OCTAVE = 4
DEFAULT_DURATION = 4
DEFAULT_REVERB = 0.25
DEFAULT_INSTRUMENT = "ocarina"
DEFAULT_ANNOUNCE = True

SAMPLE_RATE = 44100
MAX_AUDIO_CACHE_ITEMS = 20
MAX_RENDER_SECONDS = 90.0

INSTRUMENTS: dict[str, dict[str, str]] = {
    "ocarina": {
        "name_de": "Okarina",
        "name_en": "Ocarina",
    },
    "flute": {
        "name_de": "Querflöte",
        "name_en": "Flute",
    },
    "pan_flute": {
        "name_de": "Panflöte",
        "name_en": "Pan Flute",
    },
    "piano": {
        "name_de": "Klavier (Flügel)",
        "name_en": "Grand Piano",
    },
    "epiano": {
        "name_de": "E-Piano (Rhodes)",
        "name_en": "Electric Piano",
    },
    "guitar": {
        "name_de": "Akustik-Gitarre (Nylon)",
        "name_en": "Acoustic Guitar (Nylon)",
    },
    "steel_guitar": {
        "name_de": "Westerngitarre (Stahlsaiten)",
        "name_en": "Steel-String Guitar",
    },
    "electric_guitar": {
        "name_de": "E-Gitarre",
        "name_en": "Electric Guitar",
    },
    "violin": {
        "name_de": "Violine / Streicher",
        "name_en": "Violin",
    },
    "harp": {
        "name_de": "Harfe",
        "name_en": "Harp",
    },
    "music_box": {
        "name_de": "Spieluhr / Glockenspiel",
        "name_en": "Music Box / Glockenspiel",
    },
    "organ": {
        "name_de": "Orgel",
        "name_en": "Organ",
    },
    "chiptune": {
        "name_de": "8-Bit / Retro",
        "name_en": "8-Bit Chiptune",
    },
}

INSTRUMENT_IDS: list[str] = list(INSTRUMENTS.keys())

PRESETS: dict[str, dict[str, object]] = {
    "zelda_song_of_time": {
        "title": "Zelda - Hymne der Zeit (Song of Time)",
        "instrument": "ocarina",
        "bpm": 110,
        "notes": "A4:4 D4:2 F4:4 A4:4 D4:2 F4:4 A4:8 C5:8 B4:4 G4:4 F4:8 G4:8 A4:4 D4:4 C4:8 E4:8 D4:1",
    },
    "zelda_lullaby": {
        "title": "Zelda - Zeldas Wiegenlied (Zelda's Lullaby)",
        "instrument": "ocarina",
        "bpm": 108,
        "notes": "B4:2 D5:4 A4:2 G4:8 A4:8 B4:2 D5:4 A4:1 B4:2 D5:4 A5:2 G5:4 D5:2 C5:8 B4:8 A4:1",
    },
    "zelda_sarias_song": {
        "title": "Zelda - Salias Lied (Saria's Song)",
        "instrument": "ocarina",
        "bpm": 140,
        "notes": "F4:8 A4:8 B4:4 F4:8 A4:8 B4:4 F4:8 A4:8 B4:8 E5:8 D5:4 B4:8 C5:8 B4:8 G4:8 E4:2.",
    },
    "zelda_storms": {
        "title": "Zelda - Hymne des Sturms (Song of Storms)",
        "instrument": "ocarina",
        "bpm": 160,
        "notes": "D4:8 F4:8 D5:2 D4:8 F4:8 D5:2 E5:4. F5:8 E5:8 F5:8 E5:8 C5:8 A4:2.",
    },
    "zelda_secret": {
        "title": "Zelda - Geheimnis entdeckt (Secret Chime)",
        "instrument": "harp",
        "bpm": 160,
        "notes": "G5:8 F#5:8 D#5:8 A4:8 G#4:8 E5:8 G#5:8 C6:4",
    },
    "fur_elise": {
        "title": "Beethoven - Für Elise",
        "instrument": "piano",
        "bpm": 125,
        "notes": "E5:8 D#5:8 E5:8 D#5:8 E5:8 B4:8 D5:8 C5:8 A4:4 R:8 C4:8 E4:8 A4:8 B4:4 R:8 E4:8 G#4:8 B4:8 C5:4",
    },
    "spanish_romance": {
        "title": "Romanze (Akustik-Gitarre)",
        "instrument": "guitar",
        "bpm": 100,
        "notes": "E4+B4+B5:4 B4:8 B5:4 B4:8 B5:4 B4:8 A5:4 B4:8 G5:4 B4:8 G5:4 B4:8 F#5:4 B4:8 E5:4 B4:8 E4+G4+E5:2.",
    },
    "morning_mood": {
        "title": "Grieg - Morgenstimmung",
        "instrument": "flute",
        "bpm": 110,
        "notes": "B4:4 G#4:4 F#4:4 E4:4 F#4:4 G#4:4 B4:4 G#4:4 F#4:4 E4:4 F#4:8 G#4:8 F#4:8 G#4:8 B4:4 G#4:4 B4:4 C#5:4 G#4:4 C#5:4 D#5:4 B4:4 G#4:4 F#4:4 E4:2.",
    },
    "doorbell_warm": {
        "title": "Türklingel - Warmes Glockenspiel",
        "instrument": "music_box",
        "bpm": 120,
        "notes": "E5:4 C5:4 D5:4 G4:2 R:4 G4:4 D5:4 E5:4 C5:2",
    },
    "notification_success": {
        "title": "Erfolgs-Jingle (Harfe)",
        "instrument": "harp",
        "bpm": 150,
        "notes": "C5:8 E5:8 G5:8 C6:4",
    },
}

PRESET_IDS: list[str] = list(PRESETS.keys())
