"""Constants, instrument definitions, and built-in melody presets for Note Player."""

from __future__ import annotations

from typing import Any

DOMAIN = "note_player"
VERSION = "1.3.1"

STORAGE_KEY = "note_player_melodies"
STORAGE_VERSION = 1
API_AUDIO_BASE_PATH = "/api/note_player/audio"

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
DEFAULT_LIVE_NOTES = "A5:4 D5:2 F5:4 A5:4 D5:2 F5:4"

SAMPLE_RATE = 44100
MAX_AUDIO_CACHE_ITEMS = 20
MAX_RENDER_SECONDS = 90.0

INSTRUMENTS: dict[str, dict[str, Any]] = {
    "ocarina": {
        "name_de": "Okarina",
        "name_en": "Ocarina",
        "gm_program": 79,
    },
    "flute": {
        "name_de": "Querflöte",
        "name_en": "Flute",
        "gm_program": 73,
    },
    "recorder": {
        "name_de": "Blockflöte",
        "name_en": "Recorder",
        "gm_program": 74,
    },
    "pan_flute": {
        "name_de": "Panflöte",
        "name_en": "Pan Flute",
        "gm_program": 75,
    },
    "piano": {
        "name_de": "Klavier (Flügel)",
        "name_en": "Grand Piano",
        "gm_program": 0,
    },
    "epiano": {
        "name_de": "E-Piano (Rhodes)",
        "name_en": "Electric Piano",
        "gm_program": 4,
    },
    "guitar": {
        "name_de": "Akustik-Gitarre (Nylon)",
        "name_en": "Acoustic Guitar (Nylon)",
        "gm_program": 24,
    },
    "steel_guitar": {
        "name_de": "Westerngitarre (Stahlsaiten)",
        "name_en": "Steel-String Guitar",
        "gm_program": 25,
    },
    "electric_guitar": {
        "name_de": "E-Gitarre (Clean)",
        "name_en": "Electric Guitar",
        "gm_program": 27,
    },
    "violin": {
        "name_de": "Violine",
        "name_en": "Violin",
        "gm_program": 40,
    },
    "cello": {
        "name_de": "Cello",
        "name_en": "Cello",
        "gm_program": 42,
    },
    "strings": {
        "name_de": "Streicher-Ensemble",
        "name_en": "String Ensemble",
        "gm_program": 48,
    },
    "harp": {
        "name_de": "Harfe",
        "name_en": "Harp",
        "gm_program": 46,
    },
    "music_box": {
        "name_de": "Spieluhr",
        "name_en": "Music Box",
        "gm_program": 10,
    },
    "glockenspiel": {
        "name_de": "Glockenspiel",
        "name_en": "Glockenspiel",
        "gm_program": 9,
    },
    "marimba": {
        "name_de": "Marimba",
        "name_en": "Marimba",
        "gm_program": 12,
    },
    "organ": {
        "name_de": "Kirchenorgel",
        "name_en": "Church Organ",
        "gm_program": 19,
    },
    "accordion": {
        "name_de": "Akkordeon",
        "name_en": "Accordion",
        "gm_program": 21,
    },
    "trumpet": {
        "name_de": "Trompete",
        "name_en": "Trumpet",
        "gm_program": 56,
    },
    "saxophone": {
        "name_de": "Saxophon",
        "name_en": "Saxophone",
        "gm_program": 65,
    },
    "choir": {
        "name_de": "Chor (Aah)",
        "name_en": "Choir Aahs",
        "gm_program": 52,
    },
    "chiptune": {
        "name_de": "8-Bit / Retro",
        "name_en": "8-Bit Chiptune",
        "gm_program": 80,
    },
}

INSTRUMENT_IDS: list[str] = list(INSTRUMENTS.keys())

PRESETS: dict[str, dict[str, object]] = {
    "zelda_song_of_time": {
        "title": "Zelda - Hymne der Zeit (Song of Time)",
        "instrument": "ocarina",
        "bpm": 110,
        "notes": "A5:4 D5:2 F5:4 A5:4 D5:2 F5:4 A5:8 C6:8 B5:4 G5:4 F5:8 G5:8 A5:4 D5:4 C5:8 E5:8 D5:1",
    },
    "zelda_lullaby": {
        "title": "Zelda - Zeldas Wiegenlied (Zelda's Lullaby)",
        "instrument": "ocarina",
        "bpm": 108,
        "notes": "B5:2 D6:4 A5:2 G5:8 A5:8 B5:2 D6:4 A5:1 B5:2 D6:4 A6:2 G6:4 D6:2 C6:8 B5:8 A5:1",
    },
    "zelda_sarias_song": {
        "title": "Zelda - Salias Lied (Saria's Song)",
        "instrument": "ocarina",
        "bpm": 140,
        "notes": "F5:8 A5:8 B5:4 F5:8 A5:8 B5:4 F5:8 A5:8 B5:8 E6:8 D6:4 B5:8 C6:8 B5:8 G5:8 E5:2.",
    },
    "zelda_storms": {
        "title": "Zelda - Hymne des Sturms (Song of Storms)",
        "instrument": "ocarina",
        "bpm": 160,
        "notes": "D5:8 F5:8 D6:2 D5:8 F5:8 D6:2 E6:4. F6:8 E6:8 F6:8 E6:8 C6:8 A5:2.",
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
    "oot_epona": {
        "title": "Ocarina of Time - Eponas Lied",
        "instrument": "ocarina",
        "bpm": 110,
        "notes": "D6:4 B5:4 A5:2 D6:4 B5:4 A5:2",
    },
    "oot_sun": {
        "title": "Ocarina of Time - Sonnenlied",
        "instrument": "ocarina",
        "bpm": 120,
        "notes": "A5:4 F5:4 D6:2 A5:4 F5:4 D6:2",
    },
    "oot_minuet": {
        "title": "Ocarina of Time - Menuett des Waldes",
        "instrument": "ocarina",
        "bpm": 110,
        "notes": "D5:4 D6:4 B5:4 A5:4 B5:4 A5:2",
    },
    "oot_bolero": {
        "title": "Ocarina of Time - Bolero des Feuers",
        "instrument": "ocarina",
        "bpm": 120,
        "notes": "F5:8 D5:8 F5:8 D5:8 A5:8 F5:8 A5:8 F5:2",
    },
    "oot_serenade": {
        "title": "Ocarina of Time - Serenade des Wassers",
        "instrument": "ocarina",
        "bpm": 100,
        "notes": "D5:4 F5:4 A5:4 A5:4 B5:2",
    },
    "oot_requiem": {
        "title": "Ocarina of Time - Requiem der Geister",
        "instrument": "ocarina",
        "bpm": 100,
        "notes": "D5:4 F5:4 D5:4 A5:4 F5:4 D5:2",
    },
    "oot_nocturne": {
        "title": "Ocarina of Time - Nocturne der Schatten",
        "instrument": "ocarina",
        "bpm": 100,
        "notes": "B5:4 A5:4 A5:4 D5:4 B5:4 A5:4 F5:2",
    },
    "oot_prelude": {
        "title": "Ocarina of Time - Kantate des Lichts",
        "instrument": "ocarina",
        "bpm": 110,
        "notes": "D6:4 A5:4 D6:4 A5:4 B5:4 D6:2",
    },
}

PRESET_IDS: list[str] = list(PRESETS.keys())

RIFFS: dict[str, dict[str, object]] = {
    "c_major_scale": {
        "title": "C-Dur Tonleiter (C4 - C5)",
        "bpm": 130,
        "notes": "C4:8 D4:8 E4:8 F4:8 G4:8 A4:8 B4:8 C5:2",
    },
    "a_minor_arpeggio": {
        "title": "a-Moll Arpeggio",
        "bpm": 120,
        "notes": "A3:8 C4:8 E4:8 A4:8 C5:8 E5:8 A5:4 E5:8 C5:8 A4:2",
    },
    "spanish_cadence": {
        "title": "Andalusische Kadenz (Am - G - F - E)",
        "bpm": 100,
        "notes": "Am:2 Gmaj:2 Fmaj:2 Emaj:1",
    },
    "pop_chords": {
        "title": "Pop-Akkordfolge (C - G - Am - F)",
        "bpm": 105,
        "notes": "Cmaj:2 Gmaj:2 Am:2 Fmaj:2 C4+E4+G4+C5:1",
    },
    "warm_arpeggio": {
        "title": "Warme Jazz-Akkorde (Cmaj7 - Am7 - Fmaj7 - G7)",
        "bpm": 92,
        "notes": "Cmaj7:2 Am7:2 Fmaj7:2 G7:2 Cmaj7:1",
    },
    "pentatonic_lick": {
        "title": "Blues / Pentatonik-Lick",
        "bpm": 125,
        "notes": "A4:8 C5:8 D5:8 D#5:8 E5:4 G5:8 E5:8 A4:2",
    },
}

RIFF_IDS: list[str] = list(RIFFS.keys())

PAD_ITEMS: dict[str, dict[str, str]] = {
    "note_c4": {"title": "Note C4", "notes": "C4:2"},
    "note_d4": {"title": "Note D4", "notes": "D4:2"},
    "note_e4": {"title": "Note E4", "notes": "E4:2"},
    "note_f4": {"title": "Note F4", "notes": "F4:2"},
    "note_g4": {"title": "Note G4", "notes": "G4:2"},
    "note_a4": {"title": "Note A4 (Kammerton 440 Hz)", "notes": "A4:2"},
    "note_b4": {"title": "Note H4 / B4", "notes": "B4:2"},
    "note_c5": {"title": "Note C5", "notes": "C5:2"},
    "chord_cmaj": {"title": "Akkord C-Dur", "notes": "Cmaj:1"},
    "chord_dm": {"title": "Akkord d-Moll", "notes": "Dm:1"},
    "chord_em": {"title": "Akkord e-Moll", "notes": "Em:1"},
    "chord_fmaj": {"title": "Akkord F-Dur", "notes": "Fmaj:1"},
    "chord_gmaj": {"title": "Akkord G-Dur", "notes": "Gmaj:1"},
    "chord_am": {"title": "Akkord a-Moll", "notes": "Am:1"},
}
