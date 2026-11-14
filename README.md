# Note Player — Musical Instrument Synthesizer for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**Note Player** (`note_player`) is a Home Assistant custom integration that parses musical notes, chords, rests, and RTTTL ringtone strings, synthesizes realistic stereo WAV audio locally using a bundled **SoundFont 2 engine** (`py-meltysynth` + `TimGM6mb.sf2`) across **22 sampled instruments**, and plays them directly on any Home Assistant `media_player` entity (e.g., Sonos, Nest/Google Cast, Music Assistant, Squeezebox, or DLNA speakers).

> **Note:** Completely offline and local — no external TTS/cloud APIs or C libraries required.

---

## Features

- **22 Sampled SoundFont 2 Instruments** (with automatic fallback procedural synthesis, treble presence EQ, and optional custom `/config/www/note_player/custom.sf2` SoundFont support):
  - Wind & Brass: `ocarina` (Ocarina), `flute` (Flute), `recorder` (Recorder), `pan_flute` (Pan Flute), `trumpet` (Trumpet), `saxophone` (Saxophone)
  - Keys & Mallets: `piano` (Grand Piano), `epiano` (Electric Piano / Rhodes), `organ` (Church Organ), `accordion` (Accordion), `music_box` (Music Box), `glockenspiel` (Glockenspiel), `marimba` (Marimba)
  - Strings & Choir: `guitar` (Acoustic Nylon Guitar), `steel_guitar` (Steel-String Guitar), `electric_guitar` (Clean Electric Guitar), `harp` (Harp), `violin` (Violin), `cello` (Cello), `strings` (String Ensemble), `choir` (Choir Aahs)
  - Synth: `chiptune` (8-Bit Chiptune)
- **Flexible Note Notation**:
  - Standard pitch + octave + duration (e.g. `A4:4 D4:2 F4:4`)
  - Dotted notes & triplets / arbitrary beat divisions (`D5:4.`, `C5:8`)
  - German notation supported automatically (`H4`, `Ces4`, `Cis4`, `Des4`, `Dis4`, `Es4`, `Fes4`, `Fis4`, `Ges4`, `Gis4`, `As4`, `Ais4`, `Bes4`)
  - Rests (`R:4`, `P:8`, `_`)
  - Explicit polyphonic chords with strum (`C4+E4+G4:2`) and named chord symbols (`Am:2`, `G7:4`, `Fmaj7:1`, `Cmaj6:2`)
  - **RTTTL ringtone strings** (`Zelda:d=4,o=5,b=110:a,2d,f,a`)
- **10 Built-in Presets**: `zelda_song_of_time`, `zelda_lullaby`, `zelda_sarias_song`, `zelda_storms`, `zelda_secret`, `fur_elise`, `spanish_romance`, `morning_mood`, `doorbell_warm`, `notification_success`
- **Native Browse Media Integration (`media_source` + `tts`)**:
  - Open **Browse Media** on any `media_player` entity (or in the **Media** sidebar) and choose **Note Player (Instrumente & Melodien)** to browse by instrument, play presets, chords, riffs, single notes, saved melodies, or your live input notes directly on that exact speaker.
  - Or open **Browse Media → Text-to-Speech → Note Player (Noten-Eingabe)** right inside the speaker dialog to type arbitrary notes (`A5:4 D5:2 F5:4` or `bpm=140 C4+E4+G4:2`), choose any of the 22 instruments from the dropdown, and hit Play!
- **Interactive Dashboard Entities**: Creates `text`, `select`, and `number` entities (`Noten-Eingabe`, `Instrument`, `Tempo (BPM)`, `Raumhall (Reverb)`) plus persistent custom melodies (`save_melody` / `delete_melody`).
- **Built-in HTTP Audio Serving + Caching**: Serves synthesized 16-bit 44.1 kHz stereo WAV files directly from `/api/note_player/audio/{filename}` (with `HEAD`, `GET`, HTTP byte-range support, and `/config/www/note_player` backup), plus optional `announce` mode with automatic fallback if a speaker rejects `announce: true`.
- **UI Configuration & Options Flow**: Configure default speaker, instrument, BPM, reverb, and announce behavior via the Home Assistant UI.

---

## Browse Media Usage (Directly on Any Speaker)

1. Open any speaker in Home Assistant (e.g., **Media Player card → Browse Media**) so the target entity is already selected automatically.
2. **Option A — Structured Instrument Browser (`Note Player (Instrumente & Melodien)`):**
   - Pick any instrument folder (`Okarina`, `Akustik-Gitarre`, `Klavier`, etc.) to play built-in presets, riffs/scales, single notes/chords, saved custom melodies, or your current **Noten-Eingabe** text entity with one click.
3. **Option B — Direct Free-Text Note Box (`Text-to-Speech → Note Player (Noten-Eingabe)`):**
   - Pick your desired **Instrument** in the Voice dropdown.
   - Enter notes or RTTTL directly (e.g., `A4:4 D4:2 F4:4` or `bpm=145 reverb=0.4 Am:2 G7:2 Cmaj:1` or `preset=fur_elise`) and play straight to the selected speaker.
4. **Automations via `media-source://`:**
   - You can also play dynamic URIs using `media_player.play_media` with `media_content_id: "media-source://note_player/play/ocarina/110/A4:4%20D4:2%20F4:4"`.

---

## Installation

### Option 1: HACS (Custom Repository)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Limo123123&repository=ha-note-player&category=integration)

Or manually via HACS:

1. Open **HACS** in Home Assistant.
2. Open the three-dot menu (**⋮**) in the top right and select **Custom repositories**.
3. Add `https://github.com/Limo123123/ha-note-player` and choose category **Integration**.
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

Both playback services support optional service response data (`SupportsResponse.OPTIONAL`) and fire the `note_player_played` event containing `entity_id`, `instrument`, `bpm`, `duration_s`, and `url`.

### `note_player.play_midi`

Plays a Standard MIDI file (full-length songs) rendered with the SoundFont. Put `.mid` files into `/config/www/note_player/midi/` (max. 300 s). They also appear in **Browse Media → Note Player → MIDI-Dateien**. Fields: `midi_file` (file name), optional `reverb`, `volume_level`, `announce`. Each channel uses the instrument stored in the MIDI file.

### `note_player.save_melody` & `note_player.delete_melody`

Save or delete named custom melodies (`title`, `notes`, optional `instrument`, optional `bpm`) in persistent Home Assistant storage so they appear immediately in **Browse Media** under every instrument and in *Eigene gespeicherte Melodien*.

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
<summary>All 22 Instrument IDs</summary>

- `ocarina` — Ocarina
- `flute` — Flute
- `recorder` — Recorder
- `pan_flute` — Pan Flute
- `piano` — Grand Piano
- `epiano` — Electric Piano (Rhodes)
- `guitar` — Acoustic Guitar (Nylon)
- `steel_guitar` — Steel-String Guitar
- `electric_guitar` — Electric Guitar (Clean)
- `violin` — Violin
- `cello` — Cello
- `strings` — String Ensemble
- `harp` — Harp
- `music_box` — Music Box
- `glockenspiel` — Glockenspiel
- `marimba` — Marimba
- `organ` — Church Organ
- `accordion` — Accordion
- `trumpet` — Trumpet
- `saxophone` — Saxophone
- `choir` — Choir Aahs
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

- Audio is synthesized in memory (`44100 Hz`, 16-bit stereo PCM WAV) via pure-Python SoundFont 2 rendering ([sinshu/py-meltysynth](https://github.com/sinshu/py-meltysynth), MIT License) using the bundled `TimGM6mb.sf2` bank, treble presence EQ, and peak normalization + caching (up to `20` items in memory + `/config/www/note_player` disk backup).
- You can optionally drop your own `.sf2` file at `/config/www/note_player/custom.sf2` to override the bundled SoundFont.
- Maximum render length per call is capped at `90` seconds (`MAX_RENDER_SECONDS`) to prevent accidental resource exhaustion.
- Ensure your Home Assistant instance has a reachable internal/external URL configured (`Settings → System → Network`) so target speakers can fetch `/api/note_player/audio/{filename}`.

## License

MIT License — see [LICENSE](LICENSE).
