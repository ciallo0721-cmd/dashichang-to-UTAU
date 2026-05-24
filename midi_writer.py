# -*- coding: utf-8 -*-
"""
MIDI file writer for UTAU-compatible output (SMF Format 0).

Generates standard MIDI files with:
- Track 1 (control): tempo, time signature, key signature, UTAU settings
- Track 2 (notes): lyric meta events (FF 05), note on/off events

This format is directly compatible with UTAU's VSQ/MID import.
"""

import struct
from typing import List, Optional


def _write_varlen(value: int) -> bytes:
    """Encode an integer as MIDI variable-length quantity."""
    if value < 0:
        value = 0
    result = []
    result.append(value & 0x7F)
    value >>= 7
    while value:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    result.reverse()
    return bytes(result)


def _make_string_meta(event_type: int, text: str) -> bytes:
    """Create a meta event with a text string."""
    encoded = text.encode('utf-8')
    return bytes([0xFF, event_type, len(encoded)]) + encoded


def build_midi(
    notes: List[dict],
    bpm: float = 120.0,
    project_name: str = "Untitled",
    resolution: int = 480,
    time_numerator: int = 4,
    time_denominator: int = 4,
) -> bytes:
    """
    Build a complete MIDI file (SMF Format 0) from note data.

    Args:
        notes: List of dicts with keys:
            - 'pitch': MIDI note number (int)
            - 'start_tick': start position in ticks (int)
            - 'duration_ticks': duration in ticks (int)
            - 'lyric': lyric text (str), e.g. "ta", "hu"
        bpm: tempo in BPM
        project_name: project name for UTAU metadata
        resolution: ticks per quarter note (TPQN)
        time_numerator: numerator of time signature
        time_denominator: denominator of time signature

    Returns:
        Complete MIDI file as bytes
    """
    # === Sort notes by start_tick ===
    sorted_notes = sorted(notes, key=lambda n: n['start_tick'])

    # === Build Track 1 (Control/Setup track) ===
    track1_events = bytearray()

    # Track name: "Control"
    track1_events += _make_string_meta(0x03, "Control")

    # Tempo: FF 51 03 tt tt tt
    # microseconds per quarter note = 60000000 / BPM
    uspq = int(60000000.0 / bpm)
    track1_events += bytes([0xFF, 0x51, 0x03,
                           (uspq >> 16) & 0xFF,
                           (uspq >> 8) & 0xFF,
                           uspq & 0xFF])

    # Time signature: FF 58 04 nn dd cc bb
    # nn=numerator, dd=denominator(2^n), cc=MIDI clocks per metronome tick, bb=32nd notes per quarter
    den_power = 0
    d = time_denominator
    while d > 1:
        d >>= 1
        den_power += 1
    track1_events += bytes([0xFF, 0x58, 0x04,
                           time_numerator & 0xFF,
                           den_power & 0xFF,
                           0x18, 0x08])

    # Track name meta for UTAU "Setup"
    track1_events += _make_string_meta(0x06, "Setup")

    # UTAU settings
    track1_events += _make_string_meta(0x01, "Settings")

    # UTAU project name
    track1_events += _make_string_meta(0x01, f"@rem project={project_name}")

    # UTAU tempo setting (text-based, some UTAU versions read this)
    track1_events += _make_string_meta(0x01, f"@set tempo={int(bpm)}")

    # End of track
    track1_events += bytes([0xFF, 0x2F, 0x00])

    # Build Track 1 with delta times (all events at tick 0)
    track1_data = bytearray()
    track1_data += _write_varlen(0)  # delta = 0
    track1_data += track1_events

    # === Build Track 2 (Note track) ===
    track2_data = bytearray()

    # Track name: "Voice 1"
    track2_data += _write_varlen(0)
    track2_data += _make_string_meta(0x03, "Voice 1")

    # Build a list of (tick, event_bytes) for all note events
    events = []
    current_tick = 0

    for i, note in enumerate(sorted_notes):
        note_tick = note['start_tick']
        pitch = max(0, min(127, note['pitch']))
        duration = max(1, note['duration_ticks'])
        lyric = note.get('lyric', '')

        # Delta time to this note's start
        delta = note_tick - current_tick

        # Mod=0 marker (UTAU compatibility)
        mod_text = f"{i:04d}: mod=0"
        events.append((note_tick, _make_string_meta(0x01, mod_text)))

        # Lyric meta event: FF 05 len text
        # UTAU format: "1\t<phoneme>" or just "<phoneme>"
        lyric_text = f"1\t{lyric}" if lyric else "1\t"
        events.append((note_tick, _make_string_meta(0x05, lyric_text)))

        # Note On: 90 pp vv
        events.append((note_tick, bytes([0x90, pitch, 0x64])))

        # Note Off at note_tick + duration: 80 pp 00
        end_tick = note_tick + duration
        events.append((end_tick, bytes([0x80, pitch, 0x00])))

        current_tick = note_tick

    # End of track at the last note's end
    if sorted_notes:
        last_end = max(n['start_tick'] + n['duration_ticks'] for n in sorted_notes)
    else:
        last_end = 0
    events.append((last_end, bytes([0xFF, 0x2F, 0x00])))

    # Sort events by tick, then by type priority (lyrics before note on, note off before lyrics)
    def event_sort_key(evt):
        tick, data = evt
        # Note Off (80) should come first, then lyrics/meta, then Note On (90)
        if data[0] == 0x80:
            priority = 0
        elif data[0] == 0xFF:
            priority = 1
        elif data[0] == 0x90:
            priority = 2
        else:
            priority = 1
        return (tick, priority)

    events.sort(key=event_sort_key)

    # Convert to delta-time format
    prev_tick = 0
    for tick, data in events:
        delta = tick - prev_tick
        if delta < 0:
            delta = 0
        track2_data += _write_varlen(delta)
        track2_data += data
        prev_tick = tick

    # === Assemble MIDI file ===
    midi = bytearray()

    # Header chunk: MThd
    midi += b'MThd'
    midi += struct.pack('>I', 6)  # chunk length = 6
    midi += struct.pack('>H', 1)  # format 1 (multi-track)
    midi += struct.pack('>H', 2)  # 2 tracks
    midi += struct.pack('>H', resolution)  # ticks per quarter note

    # Track 1
    midi += b'MTrk'
    midi += struct.pack('>I', len(track1_data))
    midi += track1_data

    # Track 2
    midi += b'MTrk'
    midi += struct.pack('>I', len(track2_data))
    midi += track2_data

    return bytes(midi)
