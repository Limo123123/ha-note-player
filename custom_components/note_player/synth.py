"""Pure-Python / NumPy instrument synthesizer and musical note parser."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import hashlib
import io
import math
from pathlib import Path
import re
import struct
import threading
import wave

import numpy as np

from .const import (
    DEFAULT_BPM,
    DEFAULT_DURATION,
    DEFAULT_INSTRUMENT,
    DEFAULT_OCTAVE,
    DEFAULT_REVERB,
    INSTRUMENTS,
    MAX_RENDER_SECONDS,
    SAMPLE_RATE,
)
from .meltysynth import (
    MidiFile,
    MidiFileSequencer,
    SoundFont,
    Synthesizer,
    SynthesizerSettings,
    _MidiMessage,
    _MidiMessageType,
    create_buffer,
)

_BUNDLE_SOUNDFONT_PATH = Path(__file__).resolve().parent / "soundfont" / "TimGM6mb.sf2"
_CUSTOM_SOUNDFONT_PATH = Path("/config/www/note_player/custom.sf2")
_SOUNDFONT_LOCK = threading.Lock()
_SOUNDFONT_CACHE: dict[str, tuple[float, SoundFont]] = {}

# Semitone offsets from C (supports international B/Bb as well as German H).
BASE_SEMITONES: dict[str, int] = {
    "c": 0,
    "d": 2,
    "e": 4,
    "f": 5,
    "g": 7,
    "a": 9,
    "b": 11,
    "h": 11,
}

GERMAN_FLATS: dict[str, int] = {
    "ces": -1,
    "des": 1,
    "es": 3,
    "fes": 4,
    "ges": 6,
    "as": 8,
    "bes": 10,
    "hes": 10,
}

CHORD_INTERVALS: dict[str, tuple[int, ...]] = {
    "maj": (0, 4, 7),
    "dur": (0, 4, 7),
    "min": (0, 3, 7),
    "moll": (0, 3, 7),
    "dim": (0, 3, 6),
    "aug": (0, 4, 8),
    "sus2": (0, 2, 7),
    "sus4": (0, 5, 7),
    "m6": (0, 3, 7, 9),
    "maj6": (0, 4, 7, 9),
    "7": (0, 4, 7, 10),
    "maj7": (0, 4, 7, 11),
    "m7": (0, 3, 7, 10),
    "dim7": (0, 3, 6, 9),
    "add9": (0, 4, 7, 14),
}

_RTTTL_HEADER_RE = re.compile(
    r"^[^:]*:\s*(?=[^:]*(?:[dob]\s*=\s*\d+))[^:]*:.*$",
    re.IGNORECASE | re.DOTALL,
)
_RTTTL_TOKEN_RE = re.compile(
    r"^\s*(\d{1,2})?\s*(\.?)\s*([a-hp]|c#|d#|f#|g#|a#|cis|dis|fis|gis|ais|des|es|ges|as|bb|eb|ab|db|gb)\s*([#b]?)\s*(\.?)\s*(\d)?\s*(\.?)\s*$",
    re.IGNORECASE,
)
# Exclude bare '5' and '6' so octave pitches like A5 and C6 always parse as single notes.
_CHORD_NAME_RE = re.compile(
    r"^([A-GH])(#|b|is|es|s)?(maj7|maj6|add9|dim7|sus2|sus4|moll|maj|min|dim|aug|dur|m7|m6|M|m|7)(\d)?$"
)
_NOTE_RE = re.compile(
    r"^([a-gh])(is|es|[#b])?(-?\d)?$",
    re.IGNORECASE,
)
_REST_TOKENS = {"r", "p", "-", "_", "rest", "pause"}


@dataclass(frozen=True, slots=True)
class NoteEvent:
    """Single musical event (one or more simultaneous MIDI pitches, or a rest)."""

    midis: tuple[int, ...]
    beats: float


@dataclass(frozen=True, slots=True)
class WindProfile:
    """Acoustic synthesis parameters for woodwind/ocarina instruments."""

    harmonics: tuple[float, ...]
    vib_rate_hz: float
    vib_cents: float
    vib_delay_s: float
    scoop_cents: float
    scoop_tau_s: float
    attack_s: float
    release_s: float
    chiff_level: float
    air_level: float


@dataclass(frozen=True, slots=True)
class PluckedProfile:
    """Karplus-Strong physical string parameters for plucked/guitar instruments."""

    brightness: float
    damping_base: float
    damping_freq_scale: float
    pluck_ratio: float
    body_gain: float
    strum_step_s: float
    overdrive: float = 0.0


@dataclass(frozen=True, slots=True)
class ModalProfile:
    """Inharmonic/harmonic additive decay parameters for keys, harp, bells, and bowed strings."""

    ratios: tuple[float, ...]
    amps: tuple[float, ...]
    attack_s: float
    decay_rate: float
    partial_decay_slope: float
    release_s: float
    inharmonicity: float = 0.0
    unison_detune_hz: float = 0.0
    hammer_level: float = 0.0
    vib_rate_hz: float = 0.0
    vib_cents: float = 0.0
    tremolo_hz: float = 0.0
    tremolo_depth: float = 0.0
    strum_step_s: float = 0.0
    sustain_floor: float = 0.0


WIND_PROFILES: dict[str, WindProfile] = {
    "ocarina": WindProfile(
        harmonics=(1.0, 0.16, 0.04, 0.01),
        vib_rate_hz=5.4,
        vib_cents=10.0,
        vib_delay_s=0.11,
        scoop_cents=-28.0,
        scoop_tau_s=0.022,
        attack_s=0.035,
        release_s=0.075,
        chiff_level=0.06,
        air_level=0.016,
    ),
    "flute": WindProfile(
        harmonics=(1.0, 0.42, 0.20, 0.09, 0.04, 0.02),
        vib_rate_hz=6.0,
        vib_cents=14.0,
        vib_delay_s=0.14,
        scoop_cents=-16.0,
        scoop_tau_s=0.028,
        attack_s=0.055,
        release_s=0.085,
        chiff_level=0.11,
        air_level=0.032,
    ),
    "pan_flute": WindProfile(
        harmonics=(1.0, 0.08, 0.34, 0.05, 0.14, 0.03),
        vib_rate_hz=5.1,
        vib_cents=11.0,
        vib_delay_s=0.13,
        scoop_cents=-22.0,
        scoop_tau_s=0.025,
        attack_s=0.045,
        release_s=0.080,
        chiff_level=0.18,
        air_level=0.045,
    ),
}

PLUCKED_PROFILES: dict[str, PluckedProfile] = {
    "guitar": PluckedProfile(
        brightness=0.62,
        damping_base=0.9945,
        damping_freq_scale=0.000004,
        pluck_ratio=0.22,
        body_gain=0.34,
        strum_step_s=0.024,
    ),
    "steel_guitar": PluckedProfile(
        brightness=0.78,
        damping_base=0.9960,
        damping_freq_scale=0.000003,
        pluck_ratio=0.13,
        body_gain=0.26,
        strum_step_s=0.020,
    ),
    "electric_guitar": PluckedProfile(
        brightness=0.82,
        damping_base=0.9975,
        damping_freq_scale=0.000002,
        pluck_ratio=0.15,
        body_gain=0.12,
        strum_step_s=0.016,
        overdrive=2.8,
    ),
}

MODAL_PROFILES: dict[str, ModalProfile] = {
    "piano": ModalProfile(
        ratios=(1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0),
        amps=(1.0, 0.56, 0.30, 0.16, 0.09, 0.05, 0.025),
        attack_s=0.005,
        decay_rate=1.9,
        partial_decay_slope=0.45,
        release_s=0.38,
        inharmonicity=0.00022,
        unison_detune_hz=0.45,
        hammer_level=0.14,
    ),
    "epiano": ModalProfile(
        ratios=(1.0, 2.0, 3.0, 7.0, 14.0),
        amps=(1.0, 0.38, 0.14, 0.12, 0.04),
        attack_s=0.004,
        decay_rate=1.35,
        partial_decay_slope=1.15,
        release_s=0.32,
        unison_detune_hz=0.30,
        tremolo_hz=4.4,
        tremolo_depth=0.24,
    ),
    "harp": ModalProfile(
        ratios=(1.0, 2.0, 3.0, 4.0, 5.0),
        amps=(1.0, 0.52, 0.24, 0.11, 0.05),
        attack_s=0.007,
        decay_rate=1.6,
        partial_decay_slope=0.55,
        release_s=0.65,
        unison_detune_hz=0.25,
        strum_step_s=0.018,
    ),
    "music_box": ModalProfile(
        ratios=(1.0, 2.0, 2.756, 5.404),
        amps=(1.0, 0.18, 0.32, 0.10),
        attack_s=0.002,
        decay_rate=2.3,
        partial_decay_slope=0.70,
        release_s=0.85,
        hammer_level=0.12,
        strum_step_s=0.012,
    ),
    "violin": ModalProfile(
        ratios=(1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0),
        amps=(1.0, 0.62, 0.44, 0.28, 0.18, 0.11, 0.06),
        attack_s=0.10,
        decay_rate=0.05,
        partial_decay_slope=0.10,
        release_s=0.14,
        vib_rate_hz=5.8,
        vib_cents=16.0,
        sustain_floor=0.92,
    ),
    "organ": ModalProfile(
        ratios=(0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0),
        amps=(0.45, 1.0, 0.40, 0.72, 0.35, 0.45, 0.20),
        attack_s=0.012,
        decay_rate=0.0,
        partial_decay_slope=0.0,
        release_s=0.06,
        unison_detune_hz=0.55,
        tremolo_hz=6.2,
        tremolo_depth=0.14,
        sustain_floor=1.0,
    ),
}


def midi_to_freq(midi: int) -> float:
    """Convert a MIDI note number to frequency in Hertz."""
    return 440.0 * (2.0 ** ((midi - 69) / 12.0))


def _parse_single_pitch(token: str, default_octave: int) -> tuple[int, int]:
    """Parse one pitch string like 'F#5', 'Bb4', 'H', 'Cis5', or 'Es4'.

    Returns (midi_number, resolved_octave).
    """
    cleaned = token.strip()
    lower = cleaned.lower()

    if lower in GERMAN_FLATS:
        semitone = GERMAN_FLATS[lower]
        return 12 * (default_octave + 1) + semitone, default_octave

    german_flat_oct = re.match(r"^(ces|des|es|fes|ges|as|bes|hes)(-?\d)$", lower)
    if german_flat_oct:
        semitone = GERMAN_FLATS[german_flat_oct.group(1)]
        octave = int(german_flat_oct.group(2))
        return 12 * (octave + 1) + semitone, octave

    match = _NOTE_RE.match(cleaned)
    if not match:
        raise ValueError(f"Unbekannte Note: '{token}'")

    letter = match.group(1).lower()
    accidental = (match.group(2) or "").lower()
    octave = int(match.group(3)) if match.group(3) is not None else default_octave

    semitone = BASE_SEMITONES[letter]
    if accidental in ("#", "is"):
        semitone += 1
    elif accidental in ("b", "es"):
        semitone -= 1

    midi = max(21, min(108, 12 * (octave + 1) + semitone))
    return midi, octave


def _parse_chord_symbol(token: str, default_octave: int) -> tuple[int, ...] | None:
    """Try parsing a chord name like 'Am', 'Cmaj', 'G7', or 'Fmaj7'."""
    match = _CHORD_NAME_RE.match(token.strip())
    if not match:
        return None

    root_letter, accidental, quality, oct_str = match.groups()
    octave = int(oct_str) if oct_str is not None else default_octave
    root_token = f"{root_letter}{accidental or ''}{octave}"
    root_midi, _ = _parse_single_pitch(root_token, octave)

    if quality == "M":
        intervals = (0, 4, 7)
    elif quality == "m":
        intervals = (0, 3, 7)
    else:
        intervals = CHORD_INTERVALS[quality.lower()]

    return tuple(max(21, min(108, root_midi + offset)) for offset in intervals)


def _duration_code_to_beats(dur_str: str, default_duration: int) -> float:
    """Convert a duration expression like '4', '4.', '8', '16..', '*2', '/2' into beats."""
    text = dur_str.strip()
    if not text:
        return 4.0 / default_duration

    dots = len(text) - len(text.rstrip("."))
    core = text.rstrip(".")

    if core.endswith("ms") and core[:-2].replace(".", "", 1).isdigit():
        # Millisecond marker gets converted later if needed; return negative sentinel or handle cleanly.
        raise ValueError("Use standard note durations like :4, :8, :2")

    denom = float(core) if core else float(default_duration)
    if denom <= 0:
        raise ValueError(f"Ungültige Notendauer: '{dur_str}'")

    beats = 4.0 / denom
    dot_factor = 1.0
    for idx in range(dots):
        dot_factor += 0.5 ** (idx + 1)
    return beats * dot_factor


def _parse_rtttl(
    rtttl_str: str,
    default_octave: int,
    default_duration: int,
    default_bpm: int,
) -> tuple[list[NoteEvent], int]:
    """Parse an RTTTL ringtone string into NoteEvents and detected BPM."""
    parts = rtttl_str.split(":", 2)
    settings_part = parts[1]
    body_part = parts[2]

    dur = default_duration
    octave = default_octave
    bpm = default_bpm

    for item in settings_part.split(","):
        if "=" not in item:
            continue
        key, val = item.split("=", 1)
        key = key.strip().lower()
        val = val.strip()
        if key == "d" and val.isdigit():
            dur = max(1, min(64, int(val)))
        elif key == "o" and val.isdigit():
            octave = max(1, min(7, int(val)))
        elif key == "b" and val.isdigit():
            bpm = max(30, min(300, int(val)))

    events: list[NoteEvent] = []
    for raw in body_part.split(","):
        token = raw.strip()
        if not token:
            continue
        match = _RTTTL_TOKEN_RE.match(token)
        if not match:
            raise ValueError(f"Ungültiges RTTTL-Token: '{token}'")

        dur_part, dot1, pitch_part, acc, dot2, oct_part, dot3 = match.groups()
        note_dur = int(dur_part) if dur_part else dur
        dots = len(dot1) + len(dot2) + len(dot3)
        beats = (4.0 / max(1, note_dur)) * (1.5 if dots == 1 else 1.75 if dots >= 2 else 1.0)

        pitch_str = f"{pitch_part}{acc or ''}".lower()
        if pitch_str == "p":
            events.append(NoteEvent(midis=(), beats=beats))
        else:
            note_oct = int(oct_part) if oct_part else octave
            midi, _ = _parse_single_pitch(f"{pitch_str}{note_oct}", note_oct)
            events.append(NoteEvent(midis=(midi,), beats=beats))

    return events, bpm


def parse_notes(
    notes: str,
    default_octave: int = DEFAULT_OCTAVE,
    default_duration: int = DEFAULT_DURATION,
    bpm: int = DEFAULT_BPM,
) -> tuple[list[NoteEvent], int]:
    """Parse either RTTTL or custom Space/Chord note notation into NoteEvents and BPM."""
    text = (notes or "").strip()
    if not text:
        raise ValueError("Keine Noten angegeben.")

    if _RTTTL_HEADER_RE.match(text):
        return _parse_rtttl(text, default_octave, default_duration, bpm)

    # Split visual bars '|' cleanly; turn commas into explicit phrase-breath tokens.
    normalized = text.replace("|", " ").replace(";", " ").replace(",", " , ")
    tokens = [tok for tok in normalized.split() if tok]

    events: list[NoteEvent] = []
    for token in tokens:
        if token == ",":
            # Subtle breathing pause between comma-separated phrases.
            events.append(NoteEvent(midis=(), beats=0.125))
            continue

        beats = 4.0 / default_duration
        pitch_spec = token

        if ":" in token:
            pitch_spec, dur_spec = token.split(":", 1)
            beats = _duration_code_to_beats(dur_spec, default_duration)
        elif "*" in token:
            pitch_spec, mult_spec = token.split("*", 1)
            beats = (4.0 / default_duration) * float(mult_spec)
        elif "/" in token:
            pitch_spec, div_spec = token.split("/", 1)
            beats = (4.0 / default_duration) / float(div_spec)

        if pitch_spec.lower() in _REST_TOKENS:
            events.append(NoteEvent(midis=(), beats=beats))
            continue

        if "+" in pitch_spec:
            chord_midis: list[int] = []
            running_oct = default_octave
            for sub in pitch_spec.split("+"):
                if not sub.strip():
                    continue
                midi, running_oct = _parse_single_pitch(sub, running_oct)
                chord_midis.append(midi)
            if not chord_midis:
                raise ValueError(f"Ungültiger Akkord: '{token}'")
            events.append(NoteEvent(midis=tuple(sorted(chord_midis)), beats=beats))
            continue

        named_chord = _parse_chord_symbol(pitch_spec, default_octave)
        if named_chord is not None:
            events.append(NoteEvent(midis=named_chord, beats=beats))
            continue

        midi, _ = _parse_single_pitch(pitch_spec, default_octave)
        events.append(NoteEvent(midis=(midi,), beats=beats))

    if not any(ev.midis for ev in events):
        raise ValueError("Keine spielbaren Noten gefunden.")

    return events, bpm


def _first_order_lowpass(signal: np.ndarray, alpha: float) -> np.ndarray:
    """Apply a fast smoothing filter y[n] = (1 - a) * x[n] + a * y[n-1] via FFT or cumsum approximation."""
    n = signal.shape[0]
    if n < 2 or alpha <= 0.0:
        return signal
    alpha = min(0.98, max(0.01, alpha))
    # Construct exact impulse response h[k] = (1 - alpha) * alpha^k truncated to < 1e-4 energy.
    ir_len = min(n, max(16, int(math.ceil(math.log(1e-4) / math.log(alpha)))))
    k = np.arange(ir_len, dtype=np.float64)
    ir = (1.0 - alpha) * (alpha**k)
    fft_n = 1 << int(math.ceil(math.log2(n + ir_len)))
    out = np.fft.irfft(np.fft.rfft(signal, fft_n) * np.fft.rfft(ir, fft_n), fft_n)
    return out[:n]


def _synth_wind(
    freq: float,
    dur_s: float,
    profile: WindProfile,
    rng: np.random.Generator,
) -> np.ndarray:
    """Synthesize a breathy wind tone with attack pitch scoop, delayed vibrato, and air chiff."""
    total_s = dur_s + profile.release_s
    n = max(64, int(round(total_s * SAMPLE_RATE)))
    t = np.arange(n, dtype=np.float64) / SAMPLE_RATE

    # Instantaneous frequency with attack pitch scoop and delayed vibrato.
    vib_ramp = np.clip((t - profile.vib_delay_s) / 0.14, 0.0, 1.0)
    vib_lfo = np.sin(2.0 * math.pi * profile.vib_rate_hz * t)
    cents = (
        profile.scoop_cents * np.exp(-t / profile.scoop_tau_s)
        + profile.vib_cents * vib_ramp * vib_lfo
    )
    inst_freq = freq * (2.0 ** (cents / 1200.0))
    phase = 2.0 * math.pi * np.cumsum(inst_freq) / SAMPLE_RATE

    sig = np.zeros(n, dtype=np.float64)
    for k, amp in enumerate(profile.harmonics, start=1):
        if k * freq < SAMPLE_RATE * 0.44:
            sig += amp * np.sin(k * phase)

    # Shaped amplitude envelope (scale attack/release down if note is ultra-short).
    att_n = max(1, int(profile.attack_s * SAMPLE_RATE))
    rel_n = max(1, int(profile.release_s * SAMPLE_RATE))
    if att_n + rel_n >= n:
        scale = (n - 1) / max(1, att_n + rel_n)
        att_n = max(1, int(att_n * scale))
        rel_n = max(1, n - att_n)
    sus_n = max(0, n - att_n - rel_n)

    env = np.empty(n, dtype=np.float64)
    env[:att_n] = 0.5 - 0.5 * np.cos(math.pi * np.arange(att_n) / att_n)
    if sus_n > 0:
        sus_t = np.arange(sus_n) / SAMPLE_RATE
        env[att_n : att_n + sus_n] = 0.92 + 0.08 * np.exp(-sus_t / 0.18)
    tail_len = n - att_n - sus_n
    if tail_len > 0:
        end_sus = 0.92 + 0.08 * math.exp(-sus_n / (0.18 * SAMPLE_RATE)) if sus_n > 0 else 1.0
        env[att_n + sus_n :] = np.linspace(end_sus, 0.0, tail_len)

    # Breath noise: sharp attack chiff + gentle steady airflow.
    noise = rng.normal(0.0, 1.0, n)
    # Band-shape air noise above ~1.4 kHz by subtracting a heavy lowpass.
    air = noise - _first_order_lowpass(noise, 0.85)
    air = _first_order_lowpass(air, 0.55)
    chiff = profile.chiff_level * np.exp(-t / 0.032) + profile.air_level

    out = sig * env + air * chiff * np.sqrt(np.maximum(env, 0.0))
    peak = np.max(np.abs(out))
    return out / max(peak, 1e-6) * 0.85


def _synth_plucked(
    freq: float,
    dur_s: float,
    profile: PluckedProfile,
    rng: np.random.Generator,
) -> np.ndarray:
    """Synthesize a plucked string using block-vectorized Karplus-Strong with exact tuning."""
    tail_s = 0.55
    total_s = dur_s + tail_s
    target_n = max(64, int(round(total_s * SAMPLE_RATE)))

    avg_coef = 0.50 - 0.25 * profile.brightness
    ideal_period = SAMPLE_RATE / max(45.0, min(freq, 4000.0))
    delay_int = max(8, int(round(ideal_period - avg_coef)))
    actual_period = delay_int + avg_coef

    # Stretch internal render length so resampling restores exact concert pitch.
    stretch = ideal_period / actual_period
    raw_n = max(delay_int * 2, int(math.ceil(target_n * stretch)) + delay_int)
    num_blocks = int(math.ceil(raw_n / delay_int))

    # Plucked excitation burst with comb notch simulating finger/pick position on the string.
    excitation = rng.uniform(-1.0, 1.0, delay_int)
    pluck_shift = max(1, min(delay_int - 1, int(round(delay_int * profile.pluck_ratio))))
    excitation = excitation - 0.65 * np.roll(excitation, pluck_shift)
    # Smooth brightness control on initial transient.
    excitation = _first_order_lowpass(excitation, max(0.08, 0.82 - 0.68 * profile.brightness))

    # Higher notes decay slightly faster per sample, balanced cleanly across octaves.
    feedback = min(0.9985, profile.damping_base - profile.damping_freq_scale * freq)
    block_gain = feedback**delay_int

    blocks = np.empty((num_blocks, delay_int), dtype=np.float64)
    current = excitation
    last_sample = float(current[-1])

    for b in range(num_blocks):
        blocks[b] = current
        shifted = np.empty(delay_int, dtype=np.float64)
        shifted[0] = last_sample
        shifted[1:] = current[:-1]
        last_sample = float(current[-1])
        # Zero-DC loop damping preserves warmth while removing subsonic drift.
        nxt = block_gain * ((1.0 - avg_coef) * current + avg_coef * shifted)
        current = nxt - float(np.mean(nxt)) * 0.04

    raw = blocks.ravel()[:raw_n]
    raw_x = np.arange(raw_n, dtype=np.float64)
    target_x = np.linspace(0.0, (target_n - 1) / stretch, target_n, dtype=np.float64)
    out = np.interp(target_x, raw_x, raw)

    # Subtle acoustic guitar wood body resonance.
    if profile.body_gain > 0.0:
        t = np.arange(target_n, dtype=np.float64) / SAMPLE_RATE
        body = np.sin(2.0 * math.pi * 112.0 * t) * np.exp(-t / 0.055)
        out += profile.body_gain * float(np.std(out[: min(target_n, 2000)])) * body

    if profile.overdrive > 0.0:
        out = np.tanh(profile.overdrive * out)
        out = _first_order_lowpass(out, 0.45)

    # Gentle release damp starting once note duration ends.
    sus_n = min(target_n, int(round(dur_s * SAMPLE_RATE)))
    if sus_n < target_n:
        rel_len = target_n - sus_n
        out[sus_n:] *= np.exp(-np.arange(rel_len, dtype=np.float64) / (0.14 * SAMPLE_RATE))
        fade = min(rel_len, int(0.04 * SAMPLE_RATE))
        out[-fade:] *= np.linspace(1.0, 0.0, fade)

    peak = np.max(np.abs(out))
    return out / max(peak, 1e-6) * 0.85


def _synth_modal(
    freq: float,
    dur_s: float,
    profile: ModalProfile,
    rng: np.random.Generator,
) -> np.ndarray:
    """Synthesize piano, e-piano, harp, music box, violin, and organ tones."""
    total_s = dur_s + profile.release_s
    n = max(64, int(round(total_s * SAMPLE_RATE)))
    t = np.arange(n, dtype=np.float64) / SAMPLE_RATE

    if profile.vib_cents > 0.0:
        vib_ramp = np.clip((t - 0.12) / 0.14, 0.0, 1.0)
        inst_freq = freq * (2.0 ** (profile.vib_cents * vib_ramp * np.sin(2.0 * math.pi * profile.vib_rate_hz * t) / 1200.0))
        base_phase = 2.0 * math.pi * np.cumsum(inst_freq) / SAMPLE_RATE
    else:
        base_phase = 2.0 * math.pi * freq * t

    sig = np.zeros(n, dtype=np.float64)
    nyquist = SAMPLE_RATE * 0.45

    # Higher pitches ring out faster on acoustic percussive strings.
    pitch_decay_factor = 1.0 + max(0.0, (freq - 261.63) / 900.0) if profile.decay_rate > 0.2 else 1.0

    for idx, (ratio, amp) in enumerate(zip(profile.ratios, profile.amps)):
        inharm = math.sqrt(1.0 + profile.inharmonicity * (ratio**2)) if profile.inharmonicity else 1.0
        part_freq = freq * ratio * inharm
        if part_freq >= nyquist:
            continue

        partial_decay = profile.decay_rate * pitch_decay_factor * (1.0 + profile.partial_decay_slope * idx)
        if profile.sustain_floor > 0.0:
            part_env = profile.sustain_floor + (1.0 - profile.sustain_floor) * np.exp(-partial_decay * t)
        else:
            part_env = np.exp(-partial_decay * t)

        part_phase = base_phase * ratio * inharm
        if profile.unison_detune_hz > 0.0 and idx < 3:
            detune = 2.0 * math.pi * profile.unison_detune_hz * t
            wave_part = 0.5 * np.sin(part_phase) + 0.25 * np.sin(part_phase + detune) + 0.25 * np.sin(part_phase - detune)
        else:
            wave_part = np.sin(part_phase)

        sig += amp * part_env * wave_part

    if profile.hammer_level > 0.0:
        thump_noise = _first_order_lowpass(rng.normal(0.0, 1.0, n), 0.78)
        sig += profile.hammer_level * thump_noise * np.exp(-t / 0.011)

    if profile.tremolo_depth > 0.0 and profile.tremolo_hz > 0.0:
        sig *= 1.0 - profile.tremolo_depth * (0.5 - 0.5 * np.sin(2.0 * math.pi * profile.tremolo_hz * t))

    # Global attack and release envelope.
    att_n = max(1, min(n // 2, int(profile.attack_s * SAMPLE_RATE)))
    sus_n = max(att_n, min(n, int(round(dur_s * SAMPLE_RATE))))
    env = np.ones(n, dtype=np.float64)
    env[:att_n] = np.linspace(0.0, 1.0, att_n)
    if sus_n < n:
        rel_len = n - sus_n
        env[sus_n:] = np.exp(-np.linspace(0.0, 4.5, rel_len))
        fade = min(rel_len, int(0.03 * SAMPLE_RATE))
        env[-fade:] *= np.linspace(1.0, 0.0, fade)

    out = sig * env
    peak = np.max(np.abs(out))
    return out / max(peak, 1e-6) * 0.85


def _synth_chiptune(freq: float, dur_s: float) -> np.ndarray:
    """Synthesize an authentic 8-bit 25% pulse-wave retro note."""
    total_s = dur_s + 0.03
    n = max(64, int(round(total_s * SAMPLE_RATE)))
    t = np.arange(n, dtype=np.float64) / SAMPLE_RATE
    phase = (freq * t) % 1.0
    sig = np.where(phase < 0.25, 0.75, -0.25)

    att_n = min(max(1, n // 4), max(1, int(0.004 * SAMPLE_RATE)))
    sus_n = max(att_n + 1, min(n, int(round(dur_s * SAMPLE_RATE))))
    env = np.ones(n, dtype=np.float64)
    env[:att_n] = np.linspace(0.0, 1.0, att_n)
    env[att_n:sus_n] = 0.68 + 0.32 * np.exp(-np.arange(sus_n - att_n) / (0.09 * SAMPLE_RATE))
    if sus_n < n:
        env[sus_n:] = np.linspace(env[sus_n - 1], 0.0, n - sus_n)

    return sig * env * 0.55


_PROCEDURAL_ALIASES: dict[str, str] = {
    "recorder": "ocarina",
    "glockenspiel": "music_box",
    "marimba": "music_box",
    "cello": "violin",
    "strings": "violin",
    "trumpet": "organ",
    "saxophone": "flute",
    "accordion": "organ",
    "choir": "organ",
}


def _render_single_note(
    instrument: str,
    midi: int,
    dur_s: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """Dispatch procedural single-note synthesis cleanly by instrument profile."""
    resolved = _PROCEDURAL_ALIASES.get(instrument, instrument)
    freq = midi_to_freq(midi)
    if resolved in WIND_PROFILES:
        return _synth_wind(freq, dur_s, WIND_PROFILES[resolved], rng)
    if resolved in PLUCKED_PROFILES:
        return _synth_plucked(freq, dur_s, PLUCKED_PROFILES[resolved], rng)
    if resolved in MODAL_PROFILES:
        return _synth_modal(freq, dur_s, MODAL_PROFILES[resolved], rng)
    return _synth_chiptune(freq, dur_s)


def _strum_step_for(instrument: str) -> float:
    """Return chord strum arpeggiation spacing in seconds (0 if simultaneous)."""
    resolved = _PROCEDURAL_ALIASES.get(instrument, instrument)
    if resolved in PLUCKED_PROFILES:
        return PLUCKED_PROFILES[resolved].strum_step_s
    if resolved in MODAL_PROFILES:
        return MODAL_PROFILES[resolved].strum_step_s
    return 0.0


def _get_soundfont() -> SoundFont | None:
    """Load and cache the SoundFont (custom override if present, else bundled TimGM6mb.sf2)."""
    sf_path: Path | None = None
    if _CUSTOM_SOUNDFONT_PATH.is_file():
        sf_path = _CUSTOM_SOUNDFONT_PATH
    elif _BUNDLE_SOUNDFONT_PATH.is_file():
        sf_path = _BUNDLE_SOUNDFONT_PATH

    if sf_path is None:
        return None

    key = str(sf_path)
    mtime = sf_path.stat().st_mtime
    with _SOUNDFONT_LOCK:
        cached = _SOUNDFONT_CACHE.get(key)
        if cached is not None and cached[0] == mtime:
            return cached[1]
        sf = SoundFont.from_file(key)
        _SOUNDFONT_CACHE.clear()
        _SOUNDFONT_CACHE[key] = (mtime, sf)
        return sf


def _apply_presence_eq(stereo: np.ndarray) -> np.ndarray:
    """Apply linear-phase sub-bass cleanup and bright presence boost for smart speakers."""
    n = stereo.shape[1]
    if n < 64:
        return stereo

    fft_n = 1 << int(math.ceil(math.log2(n)))
    freqs = np.fft.rfftfreq(fft_n, 1.0 / SAMPLE_RATE)

    # Clean sub-60 Hz mud without thinning out acoustic fundamentals.
    sub_hp = np.clip((freqs - 45.0) / 45.0, 0.0, 1.0)
    # Smooth +3.5 dB presence/air shelf above ~1.4 kHz for crisp ocarina/flute/strings.
    shelf = 0.5 - 0.5 * np.cos(math.pi * np.clip((freqs - 1200.0) / 1800.0, 0.0, 1.0))
    presence = 1.0 + 0.45 * shelf
    # Gentle air rolloff above 15 kHz.
    top_taper = 1.0 - 0.15 * np.clip((freqs - 15000.0) / 5000.0, 0.0, 1.0)
    eq_curve = sub_hp * presence * top_taper

    out = np.empty_like(stereo)
    for ch in range(2):
        spec = np.fft.rfft(stereo[ch], fft_n)
        out[ch] = np.fft.irfft(spec * eq_curve, fft_n)[:n]
    return out


def _render_with_soundfont(
    sound_font: SoundFont,
    events: list[NoteEvent],
    instrument: str,
    bpm: int,
    reverb: float,
    progress_cb: Callable[[int], None] | None = None,
) -> np.ndarray | None:
    """Render events via pure-Python SoundFont 2 synthesis (py-meltysynth)."""
    all_midis = sorted(m for ev in events for m in ev.midis)
    if not all_midis:
        return None

    # Brighten soprano instruments if input was written in low/default octave (< C5).
    transpose = 0
    if instrument in {"ocarina", "music_box", "glockenspiel"}:
        median_midi = all_midis[len(all_midis) // 2]
        if median_midi < 72:
            transpose = 12

    sec_per_beat = 60.0 / max(30, min(300, bpm))
    lead_samples = int(0.08 * SAMPLE_RATE)
    tail_samples = int((1.10 if reverb > 0.05 else 0.45) * SAMPLE_RATE)
    max_body_samples = int(MAX_RENDER_SECONDS * SAMPLE_RATE)

    is_plucked = instrument in {"guitar", "steel_guitar", "electric_guitar", "harp"}
    strum_samples = int(0.018 * SAMPLE_RATE) if is_plucked else 0
    staccato_wind = instrument in {
        "ocarina",
        "flute",
        "pan_flute",
        "recorder",
        "violin",
        "cello",
        "strings",
        "organ",
        "accordion",
        "trumpet",
        "saxophone",
        "choir",
        "chiptune",
    }

    # Timeline tuples: (sample_idx, order_flag [0=off, 1=on], midi, velocity).
    midi_msgs: list[tuple[int, int, int, int]] = []
    cursor_s = 0.0
    last_off_sample = lead_samples

    for event in events:
        dur_s = max(0.04, event.beats * sec_per_beat)
        if cursor_s >= MAX_RENDER_SECONDS:
            break
        if event.midis:
            gate_s = dur_s * 0.93 if (staccato_wind and dur_s > 0.14) else max(0.035, dur_s - 0.012)
            vel = 114 if len(event.midis) == 1 else 104
            for idx, raw_midi in enumerate(event.midis):
                midi = max(21, min(108, raw_midi + transpose))
                on_sample = lead_samples + int(round(cursor_s * SAMPLE_RATE)) + idx * strum_samples
                off_sample = min(
                    lead_samples + max_body_samples,
                    on_sample + max(int(0.03 * SAMPLE_RATE), int(round(gate_s * SAMPLE_RATE))),
                )
                midi_msgs.append((on_sample, 1, midi, vel))
                midi_msgs.append((off_sample, 0, midi, 0))
                last_off_sample = max(last_off_sample, off_sample)
        cursor_s += dur_s

    if not midi_msgs:
        return None

    midi_msgs.sort(key=lambda item: (item[0], item[1]))
    total_samples = min(
        last_off_sample + tail_samples,
        int((MAX_RENDER_SECONDS + 2.0) * SAMPLE_RATE),
    )

    settings = SynthesizerSettings(SAMPLE_RATE)
    settings.enable_reverb_and_chorus = True
    synth = Synthesizer(sound_font, settings)

    gm_program = int(INSTRUMENTS[instrument].get("gm_program", 0))
    synth.process_midi_message(0, 0xC0, gm_program, 0)
    synth.process_midi_message(0, 0xB0, 7, 127)
    reverb_cc = max(0, min(127, int(round(max(0.0, min(1.0, float(reverb))) * 115))))
    synth.process_midi_message(0, 0xB0, 91, reverb_cc)
    chorus_cc = 28 if instrument in {"strings", "choir", "epiano", "organ", "electric_guitar"} else 8
    synth.process_midi_message(0, 0xB0, 93, chorus_cc)
    if instrument in {"ocarina", "flute", "pan_flute", "recorder", "violin", "cello", "trumpet", "saxophone"}:
        synth.process_midi_message(0, 0xB0, 1, 20)

    stereo = np.zeros((2, total_samples), dtype=np.float64)
    cursor = 0
    last_pct = 0

    for msg_sample, msg_type, midi, vel in midi_msgs:
        clamped = min(msg_sample, total_samples)
        if clamped > cursor:
            chunk = clamped - cursor
            left = create_buffer(chunk)
            right = create_buffer(chunk)
            synth.render(left, right)
            stereo[0, cursor:clamped] = np.asarray(left, dtype=np.float64)
            stereo[1, cursor:clamped] = np.asarray(right, dtype=np.float64)
            cursor = clamped
            if progress_cb is not None and total_samples > 0:
                pct = min(98, int(cursor * 100 / total_samples))
                if pct - last_pct >= 10:
                    last_pct = pct
                    progress_cb(pct)

        if msg_type == 1:
            synth.note_on(0, midi, vel)
        else:
            synth.note_off(0, midi)

    if total_samples > cursor:
        chunk = total_samples - cursor
        left = create_buffer(chunk)
        right = create_buffer(chunk)
        synth.render(left, right)
        stereo[0, cursor:total_samples] = np.asarray(left, dtype=np.float64)
        stereo[1, cursor:total_samples] = np.asarray(right, dtype=np.float64)

    if progress_cb is not None:
        progress_cb(100)

    return _apply_presence_eq(stereo)


def _apply_stereo_reverb(stereo: np.ndarray, reverb: float, rng: np.random.Generator) -> np.ndarray:
    """Apply fast FFT stereo room reverb with natural high-frequency damping."""
    reverb = max(0.0, min(1.0, float(reverb)))
    if reverb <= 0.01:
        return stereo

    ir_len = int((0.45 + 0.65 * reverb) * SAMPLE_RATE)
    t = np.arange(ir_len, dtype=np.float64) / SAMPLE_RATE
    decay_tau = 0.14 + 0.28 * reverb
    env = np.exp(-t / decay_tau)

    wet_out = np.empty_like(stereo)
    fft_n = 1 << int(math.ceil(math.log2(stereo.shape[1] + ir_len)))

    for ch in range(2):
        ir = rng.normal(0.0, 1.0, ir_len) * env
        # Inject subtle early room reflections around 18 ms and 39 ms.
        for refl_ms, refl_gain in ((17 + ch * 4, 0.35), (37 + ch * 6, 0.22)):
            idx = int(refl_ms * SAMPLE_RATE / 1000)
            if idx < ir_len:
                ir[idx] += refl_gain
        ir[: int(0.012 * SAMPLE_RATE)] = 0.0
        ir = _first_order_lowpass(ir, 0.65)
        ir /= max(np.sqrt(np.sum(ir**2)), 1e-6)

        conv = np.fft.irfft(np.fft.rfft(stereo[ch], fft_n) * np.fft.rfft(ir, fft_n), fft_n)
        wet_out[ch] = conv[: stereo.shape[1]]

    return stereo + (reverb * 0.42) * wet_out


def synthesize_notes(
    notes: str,
    instrument: str = DEFAULT_INSTRUMENT,
    bpm: int = DEFAULT_BPM,
    default_octave: int = DEFAULT_OCTAVE,
    reverb: float = DEFAULT_REVERB,
    progress_cb: Callable[[int], None] | None = None,
) -> tuple[bytes, float]:
    """Parse notes and render 16-bit stereo PCM WAV bytes plus duration in seconds.

    Returns (wav_bytes, duration_seconds).
    """
    if instrument not in INSTRUMENTS:
        raise ValueError(f"Unbekanntes Instrument: '{instrument}'. Verfügbar: {', '.join(INSTRUMENTS)}")

    if progress_cb is not None:
        progress_cb(0)

    events, resolved_bpm = parse_notes(
        notes=notes,
        default_octave=default_octave,
        default_duration=DEFAULT_DURATION,
        bpm=bpm,
    )

    sound_font = _get_soundfont()
    stereo: np.ndarray | None = None
    if sound_font is not None:
        stereo = _render_with_soundfont(
            sound_font, events, instrument, resolved_bpm, reverb, progress_cb=progress_cb
        )

    if stereo is not None:
        total_samples = stereo.shape[1]
    else:
        sec_per_beat = 60.0 / max(30, min(300, resolved_bpm))
        lead_pad_s = 0.15
        tail_pad_s = 0.90 if reverb > 0.05 else 0.35

        # Compute deterministic seed so identical note requests sound identical & cache cleanly.
        seed_bytes = hashlib.sha256(f"{instrument}:{resolved_bpm}:{notes}".encode()).digest()[:8]
        rng = np.random.default_rng(int.from_bytes(seed_bytes, "big"))

        # Schedule note renders within MAX_RENDER_SECONDS.
        scheduled: list[tuple[int, np.ndarray, float]] = []
        cursor_s = lead_pad_s
        strum_step = _strum_step_for(instrument)
        max_sample = 0

        for event in events:
            dur_s = max(0.04, event.beats * sec_per_beat)
            if cursor_s >= MAX_RENDER_SECONDS:
                break
            if event.midis:
                num_voices = len(event.midis)
                chord_scale = 1.0 / math.sqrt(num_voices)
                for idx, midi in enumerate(event.midis):
                    onset_s = cursor_s + idx * strum_step
                    # Slight natural duration reduction for staccato articulation on pure wind tones.
                    render_dur = dur_s * 0.94 if (instrument in WIND_PROFILES and dur_s > 0.18) else dur_s
                    voice = _render_single_note(instrument, midi, render_dur, rng) * chord_scale
                    start_idx = int(round(onset_s * SAMPLE_RATE))
                    end_idx = start_idx + voice.shape[0]
                    max_sample = max(max_sample, end_idx)
                    pan = 0.0 if num_voices == 1 else -0.22 + 0.44 * (idx / max(1, num_voices - 1))
                    scheduled.append((start_idx, voice, pan))
            cursor_s += dur_s

        if not scheduled:
            raise ValueError("Keine Noten innerhalb der maximalen Render-Dauer gefunden.")

        total_samples = max(max_sample, int(round((cursor_s + tail_pad_s) * SAMPLE_RATE)))
        total_samples = min(total_samples, int((MAX_RENDER_SECONDS + 2.0) * SAMPLE_RATE))
        stereo = np.zeros((2, total_samples), dtype=np.float64)

        for start_idx, voice, pan in scheduled:
            if start_idx >= total_samples:
                continue
            take = min(voice.shape[0], total_samples - start_idx)
            gain_l = math.cos((pan + 1.0) * math.pi / 4.0)
            gain_r = math.sin((pan + 1.0) * math.pi / 4.0)
            stereo[0, start_idx : start_idx + take] += gain_l * voice[:take]
            stereo[1, start_idx : start_idx + take] += gain_r * voice[:take]

        stereo = _apply_stereo_reverb(stereo, reverb, rng)
        if progress_cb is not None:
            progress_cb(100)

    # Gentle soft-clipping headroom + normalization.
    peak = float(np.max(np.abs(stereo)))
    if peak > 1e-6:
        stereo = np.tanh((stereo / peak) * 1.15) / math.tanh(1.15) * 0.90

    interleaved = np.column_stack((stereo[0], stereo[1]))
    pcm16 = np.clip(interleaved * 32767.0, -32768, 32767).astype("<i2")

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm16.tobytes())

    duration_s = round(total_samples / SAMPLE_RATE, 2)
    return buf.getvalue(), duration_s


MAX_MIDI_SECONDS = 300.0


def _override_midi_instrument(midi: MidiFile, instrument: str) -> None:
    """Rewrite a MidiFile's messages to force all melodic channels to a single GM instrument."""
    gm_program = int(INSTRUMENTS[instrument].get("gm_program", 0))
    orig_messages = list(midi._messages)  # noqa: SLF001
    orig_times = list(midi._times)  # noqa: SLF001

    # Check if there are any melodic note-on events (ch != 9).
    melodic_pitches: list[int] = [
        msg.data1
        for msg in orig_messages
        if msg.type == _MidiMessageType.NORMAL
        and msg.channel != 9
        and msg.command == 0x90
        and msg.data2 > 0
    ]
    has_melodic = len(melodic_pitches) > 0

    # Auto-brighten soprano instruments if the MIDI melody is written in a low octave.
    transpose = 0
    if has_melodic and instrument in {"ocarina", "music_box", "glockenspiel"}:
        sorted_p = sorted(melodic_pitches)
        median_p = sorted_p[len(sorted_p) // 2]
        if median_p < 65:
            transpose = 12

    new_messages: list[_MidiMessage] = []
    new_times: list[float] = []

    for msg, t in zip(orig_messages, orig_times):
        if msg.type != _MidiMessageType.NORMAL:
            new_messages.append(msg)
            new_times.append(t)
            continue

        ch = msg.channel
        cmd = msg.command
        d1 = msg.data1
        d2 = msg.data2

        if ch == 9:
            if has_melodic:
                # Mute percussion channel so the solo instrument plays cleanly without drum hits.
                continue
            ch = 0

        if cmd == 0xC0:
            # Force Program Change to the chosen instrument.
            new_messages.append(_MidiMessage(ch, 0xC0, gm_program, 0))
            new_times.append(t)
            continue

        if cmd == 0xB0 and d1 in (0x00, 0x20):
            # Ignore Bank Select MSB/LSB so the channel stays in GM Bank 0.
            continue

        if transpose and cmd in (0x80, 0x90):
            d1 = max(21, min(108, d1 + transpose))

        new_messages.append(_MidiMessage(ch, cmd, d1, d2))
        new_times.append(t)

    midi._messages = new_messages  # noqa: SLF001
    midi._times = new_times  # noqa: SLF001


def render_midi(
    midi_bytes: bytes,
    reverb: float = DEFAULT_REVERB,
    instrument: str | None = None,
    progress_cb: Callable[[int], None] | None = None,
) -> tuple[bytes, float]:
    """Render a Standard MIDI File with the SoundFont and return (wav_bytes, duration_seconds)."""
    sound_font = _get_soundfont()
    if sound_font is None:
        raise ValueError("Kein SoundFont gefunden - MIDI-Wiedergabe nicht möglich.")

    if instrument is not None and instrument != "original" and instrument not in INSTRUMENTS:
        raise ValueError(
            f"Unbekanntes Instrument: '{instrument}'. Verfügbar: {', '.join(INSTRUMENTS)}"
        )

    if progress_cb is not None:
        progress_cb(0)

    try:
        midi = MidiFile(io.BytesIO(midi_bytes))
    except Exception as err:  # noqa: BLE001
        raise ValueError(f"Ungültige MIDI-Datei: {err}") from err

    length_s = float(midi.length)
    if length_s <= 0.0:
        raise ValueError("MIDI-Datei enthält keine Noten.")
    if length_s > MAX_MIDI_SECONDS:
        raise ValueError(
            f"MIDI-Datei ist zu lang ({length_s:.0f}s, maximal {MAX_MIDI_SECONDS:.0f}s)."
        )

    override_inst = instrument if (instrument and instrument in INSTRUMENTS) else None
    if override_inst is not None:
        _override_midi_instrument(midi, override_inst)

    settings = SynthesizerSettings(SAMPLE_RATE)
    settings.enable_reverb_and_chorus = reverb > 0.05
    synth = Synthesizer(sound_font, settings)
    sequencer = MidiFileSequencer(synth)
    sequencer.play(midi, False)

    if override_inst is not None:
        gm_program = int(INSTRUMENTS[override_inst].get("gm_program", 0))
        reverb_cc = max(0, min(127, int(round(max(0.0, min(1.0, float(reverb))) * 115))))
        chorus_cc = (
            28
            if override_inst in {"strings", "choir", "epiano", "organ", "electric_guitar"}
            else 8
        )
        add_mod = override_inst in {
            "ocarina",
            "flute",
            "pan_flute",
            "recorder",
            "violin",
            "cello",
            "trumpet",
            "saxophone",
        }
        for ch in range(16):
            if ch == 9:
                continue
            synth.process_midi_message(ch, 0xB0, 0x00, 0)
            synth.process_midi_message(ch, 0xC0, gm_program, 0)
            synth.process_midi_message(ch, 0xB0, 91, reverb_cc)
            synth.process_midi_message(ch, 0xB0, 93, chorus_cc)
            if add_mod:
                synth.process_midi_message(ch, 0xB0, 1, 18)

    total = int((length_s + (2.0 if reverb > 0.05 else 0.8)) * SAMPLE_RATE)
    stereo = np.zeros((2, total), dtype=np.float32)
    chunk = SAMPLE_RATE
    pos = 0
    last_pct = 0
    while pos < total:
        n = min(chunk, total - pos)
        left = create_buffer(n)
        right = create_buffer(n)
        sequencer.render(left, right)
        stereo[0, pos : pos + n] = np.asarray(left, dtype=np.float32)
        stereo[1, pos : pos + n] = np.asarray(right, dtype=np.float32)
        pos += n
        if progress_cb is not None and total > 0:
            pct = min(99, int(pos * 100 / total))
            if pct - last_pct >= 5:
                last_pct = pct
                progress_cb(pct)

    if override_inst is not None:
        stereo = _apply_presence_eq(stereo.astype(np.float64)).astype(np.float32)

    peak = float(np.max(np.abs(stereo)))
    if peak > 1e-6:
        stereo = stereo / peak * 0.9

    if progress_cb is not None:
        progress_cb(100)

    pcm16 = np.clip(stereo.T * 32767.0, -32768, 32767).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm16.tobytes())
    return buf.getvalue(), round(total / SAMPLE_RATE, 2)
