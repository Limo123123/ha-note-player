# Note Player — Musical Instrument Synthesizer for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**Note Player** (`note_player`) is a Home Assistant custom integration that parses musical notes, chords, rests, and RTTTL ringtone strings, synthesizes realistic stereo WAV audio locally in Python/NumPy across **13 instruments**, and plays them directly on any Home Assistant `media_player` entity (e.g., Sonos, Nest/Google Cast, Music Assistant, Squeezebox, or DLNA speakers).

> **Note:** Completely offline and local — no external TTS/cloud APIs or pre-recorded sound files required.

---

## Features

- **13 Synthesized Instruments** using physical modeling, additive synthesis, FM/modal synthesis, Karplus-Strong plucked strings, and 8-bit retro waveforms:
  - Wind: `ocarina` (Ocarina), `flute` (Flute), `pan_flute` (Pan Flute)
  - Keys: `piano` (Grand Piano), `epiano` (Electric Piano / Rhodes), `organ` (Organ), `music_box` (Music Box / Glockenspiel)
  - Plucked / Bowed Strings: `guitar` (Acoustic Nylon Guitar), `steel_guitar` (Steel-String Guitar), `electric_guitar` (Electric Guitar), `harp` (Harp), `violin` (Violin)
  - Synth: `chiptune` (8-Bit Chiptune)
- **Flexible Note Notation**:
  - Standard pitch + octave + duration (e.g. `A4:4 D4:2 F4:4`)
  - Dotted notes & triplets / arbitrary beat divisions (`D5:4.`, `C5:8`)
  - German notation supported automatically (`H4`, `Ces4`, `Cis4`, `Des4`, `Dis4`, `Es4`, `Fes4`, `Fis4`, `Ges4`, `Gis4`, `As4`, `Ais4`, `Bes4`)
  - Rests (`R:4`, `P:8`, `_`)
  - Explicit polyphonic chords with strum (`C4+E4+G4:2`) and named chord symbols (`Am:2`, `G7:4`, `Fmaj7:1`, `Cmaj6:2`)
  - **RTTTL ringtone strings** (`Zelda:d=4,o=5,b=110:a,2d,f,a`)
- **10 Built-in Presets**: `zelda_song_of_time`, `zelda_lullaby`, `zelda_sarias_song`, `zelda_storms`, `zelda_secret`, `fur_elise`, `spanish_romance`, `morning_mood`, `doorbell_warm`, `notification_success`
- **Built-in HTTP Audio Serving + Caching**: Serves synthesized 16-bit 44.1 kHz stereo WAV files directly from `/api/note_player/audio/{filename}` (with `HEAD`, `GET`, HTTP byte-range support, and `/config/www/note_player` backup), plus optional `announce` mode with automatic fallback if a speaker rejects `announce: true`.
- **UI Configuration & Options Flow**: Configure default speaker, instrument, BPM, reverb, and announce behavior via the Home Assistant UI.

---

## Installation

### Option 1: HACS (Custom Repository)

1. Open **HACS** in Home Assistant.
2. Open the three-dot menu (**⋮**) in the top right and select **Custom repositories**.
3. Add this repository URL and choose category **Integration**.
4. Click **Add**, find **Note Player** in HACS, and click **Download**.
5. Restart Home Assistant.
6. Go to **Settings → Devices & Services → Add Integration** and search for **Note Player**.

### Option 2: Manual Installation

1. Copy `custom_components/note_player` into your Home Assistant `/config/custom_components/note_player` directory.
2. Restart Home Assistant.
3. Add **Note Player** under **Settings → Devices & Services → Add Integration**.

---

## Services

### `note_player.play_notes`

Synthesizes and plays a custom note, chord, or RTTTL sequence.

| Field | Required | Default | Description |
| :--- | :--- | :--- | :--- |
| `notes` | Yes | — | Notes, chords, rests, or RTTTL string |
| `instrument` | No | Configured default (`ocarina`) | Instrument ID (see list below) |
| `bpm` | No | Configured default (`120`) | Tempo in BPM (`30`–`300`) |
| `octave` | No | `4` | Default octave (`1`–`7`) when omitted on a note |
| `reverb` | No | Configured default (`0.25`) | Natural stereo room reverb (`0.0`–`1.0`) |
| `volume_level` | No | — | Optional speaker volume before playback (`0.0`–`1.0`) |
| `announce` | No | Configured default (`true`) | Play as announcement when supported by the target speaker |

### `note_player.play_preset`

Plays one of the 10 built-in melodies (`preset`), optionally overriding `instrument`, `bpm`, `reverb`, `volume_level`, or `announce`.

Both services support optional service response data (`SupportsResponse.OPTIONAL`) and fire the `note_player_played` event containing `entity_id`, `instrument`, `bpm`, `duration_s`, and `url`.

---

## Note Syntax Guide

Notes are whitespace-separated (spaces, newlines, or commas).

| Syntax | Meaning | Example |
| :--- | :--- | :--- |
| `<Pitch><Octave>:<Dur>` | Standard note (`1`=whole, `2`=half, `4`=quarter, `8`=eighth, `16`, `32`) | `A4:4 C#5:8 Eb5:2` |
| `<Note>.` | Dotted duration (1.5x length) | `D5:4.` or `E4:2.` |
| `R:<Dur>` / `P:<Dur>` | Rest / Pause | `R:4` or `P:8` |
| `H4`, `Cis5`, `Es4` | German notation (`H` = `B`, `is` = `#`, `es` = `b`) | `H4:4 Cis5:8 Es4:4` |
| `<N1>+<N2>+<N3>:<Dur>` | Explicit chord (slightly strummed on plucked instruments) | `C4+E4+G4:2` |
| `<Root><Quality>:<Dur>` | Named chord (`m`, `maj`, `min`, `dim`, `aug`, `sus2`, `sus4`, `7`, `maj7`, `m7`, `maj6`) | `Am:2 G7:2 Fmaj7:1` |
| RTTTL | Classic ringtone syntax | `Zelda:d=4,o=5,b=110:a,2d,f,a` |

---

## Automation Examples

### Play a Zelda Ocarina Melody on Doorbell Press

```yaml
alias: "Doorbell Ocarina Chime"
trigger:
  - platform: state
    entity_id: binary_sensor.front_door_bell
    to: "on"
action:
  - action: note_player.play_notes
    target:
      entity_id: media_player.living_room_speaker
    data:
      instrument: ocarina
      bpm: 110
      reverb: 0.35
      announce: true
      notes: >
        A4:4 D4:2 F4:4 A4:4 D4:2 F4:4
        A4:8 C5:8 B4:4 G4:4 F4:8 G4:8 A4:4 D4:4 C4:8 E4:8 D4:1
```

### Play Acoustic Guitar Chords for Good Morning

```yaml
action: note_player.play_notes
target:
  entity_id: media_player.living_room_speaker
data:
  instrument: guitar
  bpm: 95
  reverb: 0.3
  notes: "Am:2 Fmaj7:2 Cmaj:2 G7:2 C4+E4+G4+C5:1"
```

### Trigger a Built-in Preset

```yaml
action: note_player.play_preset
target:
  entity_id: media_player.living_room_speaker
data:
  preset: zelda_secret
  instrument: harp
```

---

## Instruments & Presets

<details>
<summary>All 13 Instrument IDs</summary>

- `ocarina` — Ocarina
- `flute` — Flute
- `pan_flute` — Pan Flute
- `piano` — Grand Piano
- `epiano` — Electric Piano (Rhodes)
- `guitar` — Acoustic Guitar (Nylon)
- `steel_guitar` — Steel-String Guitar
- `electric_guitar` — Electric Guitar
- `violin` — Violin
- `harp` — Harp
- `music_box` — Music Box / Glockenspiel
- `organ` — Organ
- `chiptune` — 8-Bit Chiptune

</details>

<details>
<summary>All 10 Built-in Presets</summary>

- `zelda_song_of_time` — Zelda - Song of Time (`ocarina`, 110 BPM)
- `zelda_lullaby` — Zelda - Zelda's Lullaby (`ocarina`, 108 BPM)
- `zelda_sarias_song` — Zelda - Saria's Song (`ocarina`, 140 BPM)
- `zelda_storms` — Zelda - Song of Storms (`ocarina`, 160 BPM)
- `zelda_secret` — Zelda - Secret Chime (`harp`, 160 BPM)
- `fur_elise` — Beethoven - Für Elise (`piano`, 125 BPM)
- `spanish_romance` — Spanish Romance (`guitar`, 100 BPM)
- `morning_mood` — Grieg - Morning Mood (`flute`, 110 BPM)
- `doorbell_warm` — Doorbell - Warm Glockenspiel (`music_box`, 120 BPM)
- `notification_success` — Success Notification Jingle (`harp`, 150 BPM)

</details>

---

## Technical Notes

- Audio is synthesized in memory (`44100 Hz`, 16-bit stereo PCM WAV, peak-normalized with gentle soft limiting) and cached (up to `20` items in memory + `/config/www/note_player` disk backup).
- Maximum render length per call is capped at `90` seconds (`MAX_RENDER_SECONDS`) to prevent accidental resource exhaustion.
- Ensure your Home Assistant instance has a reachable internal/external URL configured (`Settings → System → Network`) so target speakers can fetch `/api/note_player/audio/{filename}`.

## License

MIT License — see [LICENSE](LICENSE).
