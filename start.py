#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dashichang-to-UTAU - Convert Dashichang project files to UTAU formats.

This is a merged standalone version of:
- converter.py  : DSC / UFDATA parsing
- midi_writer.py: UTAU-compatible MIDI (SMF Format 1) generation
- ust_writer.py : UST file generation
- start.py      : CLI entry point

Usage:
    python dashichang_to_utau.py

Supported input: .dsc (Chinese-keyed JSON) or .ufdata (English-keyed JSON)
Output formats: .mid (MIDI), .ust (UTAU Sequence Text), or both

Author: ciallo0721-cmd
License: MIT
"""

import os
import sys
import struct
import json
from typing import List, Optional

# ============================================================================
#  Helper functions (MIDI variable-length, string meta)
# ============================================================================

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
    """Create a meta event with a text string. Length uses variable-length quantity."""
    encoded = text.encode('utf-8')
    length_bytes = _write_varlen(len(encoded))
    return bytes([0xFF, event_type]) + length_bytes + encoded


# ============================================================================
#  MIDI writer (from midi_writer.py)
# ============================================================================

def build_midi(
    notes: List[dict],
    bpm: float = 120.0,
    project_name: str = "Untitled",
    resolution: int = 480,
    time_numerator: int = 4,
    time_denominator: int = 4,
) -> bytes:
    """
    Build a complete MIDI file (SMF Format 1) from note data.

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
    sorted_notes = sorted(notes, key=lambda n: n['start_tick'])

    # === Build Track 1 (Control/Setup track) ===
    track1_events = bytearray()

    track1_events += _make_string_meta(0x03, "Control")

    uspq = int(60000000.0 / bpm)
    track1_events += bytes([0xFF, 0x51, 0x03,
                           (uspq >> 16) & 0xFF,
                           (uspq >> 8) & 0xFF,
                           uspq & 0xFF])

    den_power = 0
    d = time_denominator
    while d > 1:
        d >>= 1
        den_power += 1
    track1_events += bytes([0xFF, 0x58, 0x04,
                           time_numerator & 0xFF,
                           den_power & 0xFF,
                           0x18, 0x08])

    track1_events += _make_string_meta(0x06, "Setup")
    track1_events += _make_string_meta(0x01, "Settings")
    track1_events += _make_string_meta(0x01, f"@rem project={project_name}")
    track1_events += _make_string_meta(0x01, f"@set tempo={int(bpm)}")
    track1_events += bytes([0xFF, 0x2F, 0x00])

    track1_data = bytearray()
    track1_data += _write_varlen(0)
    track1_data += track1_events

    # === Build Track 2 (Note track) ===
    track2_data = bytearray()
    track2_data += _write_varlen(0)
    track2_data += _make_string_meta(0x03, "Voice 1")

    events = []
    current_tick = 0

    for i, note in enumerate(sorted_notes):
        note_tick = note['start_tick']
        pitch = max(0, min(127, note['pitch']))
        duration = max(1, note['duration_ticks'])
        lyric = note.get('lyric', '')

        delta = note_tick - current_tick
        mod_text = f"{i:04d}: mod=0"
        events.append((note_tick, _make_string_meta(0x01, mod_text)))
        lyric_text = f"1\t{lyric}" if lyric else "1\t"
        events.append((note_tick, _make_string_meta(0x05, lyric_text)))
        events.append((note_tick, bytes([0x90, pitch, 0x64])))
        end_tick = note_tick + duration
        events.append((end_tick, bytes([0x80, pitch, 0x00])))
        current_tick = note_tick

    if sorted_notes:
        last_end = max(n['start_tick'] + n['duration_ticks'] for n in sorted_notes)
    else:
        last_end = 0
    events.append((last_end, bytes([0xFF, 0x2F, 0x00])))

    def event_sort_key(evt):
        tick, data = evt
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
    midi += b'MThd'
    midi += struct.pack('>I', 6)
    midi += struct.pack('>H', 1)      # format 1
    midi += struct.pack('>H', 2)      # 2 tracks
    midi += struct.pack('>H', resolution)
    midi += b'MTrk'
    midi += struct.pack('>I', len(track1_data))
    midi += track1_data
    midi += b'MTrk'
    midi += struct.pack('>I', len(track2_data))
    midi += track2_data

    return bytes(midi)


# ============================================================================
#  UST writer (from ust_writer.py)
# ============================================================================

def midi_note_to_name(note_num: int) -> str:
    """Convert MIDI note number to note name (e.g. 60 -> C4, 57 -> A3)."""
    note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    octave = (note_num // 12) - 1
    note_name = note_names[note_num % 12]
    return f"{note_name}{octave}"


def build_ust(
    notes: List[dict],
    bpm: float = 120.0,
    project_name: str = "Untitled",
    voice_dir: str = "",
    resolution: int = 480,
) -> str:
    """
    Build a UST file string from note data.

    Args:
        notes: List of dicts with keys:
            - 'pitch': MIDI note number (int)
            - 'start_tick': start position in ticks
            - 'duration_ticks': duration in ticks
            - 'lyric': lyric text (str)
        bpm: tempo in BPM
        project_name: project name
        voice_dir: voicebank directory path (optional)
        resolution: ticks per quarter note

    Returns:
        Complete UST file as string
    """
    if not notes:
        return "[#SETTINGS]\nTempo=120.00\nVoiceDir=\nOutfile=output.wav\nCacheDir=\nMode2=True\n"

    lines = []
    lines.append("[#SETTINGS]")
    lines.append(f"Tempo={bpm:.2f}")
    lines.append(f"VoiceDir={voice_dir}")
    lines.append("Outfile=")
    lines.append("CacheDir=")
    lines.append("Mode2=True")

    sorted_notes = sorted(notes, key=lambda n: n['start_tick'])
    ms_per_tick = (60000.0 / bpm) / resolution

    for i, note in enumerate(sorted_notes):
        duration_ticks = max(1, note['duration_ticks'])
        lyric = note.get('lyric', '-')
        if lyric == '-' or not lyric.strip():
            lyric = 'R'

        note_name = midi_note_to_name(note['pitch'])
        duration_ms = duration_ticks * ms_per_tick
        length_ms = max(1, int(duration_ms))

        lines.append("")
        lines.append(f"[#{i:04d}]")
        lines.append(f"Lyric={lyric}")
        lines.append(f"Alias=")
        lines.append(f"Offset=0")
        lines.append(f"Consonant=0")
        lines.append(f"Cutoff=0")
        lines.append("")
        lines.append(f"Envelope=0,5,0,100,100,0")
        lines.append("")
        lines.append(f"@f2={note_name}")
        lines.append(f"@p2={length_ms}")

    return '\n'.join(lines) + '\n'


# ============================================================================
#  DSC / UFDATA parser (from converter.py)
# ============================================================================

def load_json_file(filepath: str) -> dict:
    """Load and parse a JSON file, handling BOM."""
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        return json.load(f)


def parse_ufdata(filepath: str) -> dict:
    """
    Parse an UFDATA file (English-keyed JSON).

    Returns dict with:
        - 'notes': list of note dicts (pitch, start_tick, duration_ticks, lyric)
        - 'bpm': tempo
        - 'project_name': project name
        - 'time_numerator', 'time_denominator': time signature
        - 'resolution': ticks per quarter note (480 for UFDATA)
    """
    data = load_json_file(filepath)
    project = data.get('project', {})

    bpm = 120.0
    time_num = 4
    time_den = 4
    resolution = 480

    tempos = project.get('tempos', [])
    if tempos:
        bpm = tempos[0].get('bpm', 120.0)

    ts_list = project.get('timeSignatures', [])
    if ts_list:
        time_num = ts_list[0].get('numerator', 4)
        time_den = ts_list[0].get('denominator', 4)

    project_name = project.get('name', 'Untitled')

    notes = []
    tracks = project.get('tracks', [])
    for track in tracks:
        track_notes = track.get('notes', [])
        for n in track_notes:
            pitch = n.get('key', 60)
            start_tick = n.get('tickOn', 0)
            end_tick = n.get('tickOff', 480)
            duration = max(1, end_tick - start_tick)
            lyric = n.get('lyric', '')
            notes.append({
                'pitch': int(round(pitch)),
                'start_tick': int(start_tick),
                'duration_ticks': int(duration),
                'lyric': lyric,
            })

    return {
        'notes': notes,
        'bpm': bpm,
        'project_name': project_name,
        'time_numerator': time_num,
        'time_denominator': time_den,
        'resolution': resolution,
    }


def parse_dsc(filepath: str) -> dict:
    """
    Parse a DSC file (Chinese-keyed JSON).

    DSC uses continuous pitch values (float semitones) and beat-based durations.
    We convert to MIDI ticks (480 TPQN).

    Returns same structure as parse_ufdata.
    """
    data = load_json_file(filepath)

    bpm = 120.0
    time_num = 4
    time_den = 4
    resolution = 480
    project_name = data.get('歌曲名称', data.get('文件名', 'Untitled'))

    ts = data.get('拍号', {})
    if isinstance(ts, dict):
        time_num = ts.get('分子', 4)
        time_den = ts.get('分母', 4)

    vocal_tracks = data.get('声乐曲', [])
    if vocal_tracks:
        first_track = vocal_tracks[0]
        track_bpm = first_track.get('每分钟拍数', None)
        if track_bpm is not None:
            bpm = float(track_bpm)

    notes = []
    current_tick = 0

    for track in vocal_tracks:
        track_notes = track.get('音符', [])
        for note in track_notes:
            pronunciation = note.get('音节发音', {})
            is_rest = pronunciation.get('休止符', False)
            if is_rest:
                duration_beats = note.get('时长', 0.5)
                current_tick += int(duration_beats * resolution)
                continue

            raw_pitch = note.get('音高', 60.0)
            midi_pitch = int(round(raw_pitch))

            duration_beats = note.get('时长', 0.5)
            duration_ticks = max(1, int(duration_beats * resolution))

            lyric_text = pronunciation.get('原文', '')
            display_text = pronunciation.get('音符显示', lyric_text)
            lyric = display_text if display_text else lyric_text
            if not lyric:
                lyric = '-'

            notes.append({
                'pitch': max(0, min(127, midi_pitch)),
                'start_tick': current_tick,
                'duration_ticks': duration_ticks,
                'lyric': lyric,
            })

            current_tick += duration_ticks

    return {
        'notes': notes,
        'bpm': float(bpm),
        'project_name': project_name,
        'time_numerator': time_num,
        'time_denominator': time_den,
        'resolution': resolution,
    }


def detect_format(filepath: str) -> str:
    """
    Auto-detect file format based on content.

    Returns: 'ufdata', 'dsc', or raises ValueError
    """
    try:
        data = load_json_file(filepath)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError("File is not valid JSON")

    if 'formatVersion' in data:
        return 'ufdata'
    if '文件签名' in data or '声乐曲' in data or '音符' in data:
        return 'dsc'
    raise ValueError("Unknown file format: cannot detect DSC or UFDATA structure")


def parse_file(filepath: str) -> dict:
    """
    Parse a DSC or UFDATA file, auto-detecting format.

    Returns parsed data in unified format.
    """
    fmt = detect_format(filepath)
    if fmt == 'ufdata':
        return parse_ufdata(filepath)
    elif fmt == 'dsc':
        return parse_dsc(filepath)
    else:
        raise ValueError(f"Unsupported format: {fmt}")


# ============================================================================
#  CLI entry point (from start.py)
# ============================================================================

def print_banner():
    print("=" * 50)
    print("  dashichang-to-UTAU")
    print("  Author: ciallo0721-cmd")
    print("  Convert Dashichang .dsc/.ufdata to MIDI/UST")
    print("=" * 50)
    print()


def get_input_path() -> str:
    """Get the input file path from user."""
    while True:
        path = input("Input file path (.dsc or .ufdata): ").strip().strip('"').strip("'")
        if not path:
            print("Error: path cannot be empty.")
            continue
        if not os.path.isfile(path):
            print(f"Error: file not found: {path}")
            continue
        return os.path.abspath(path)


def get_output_dir() -> Optional[str]:
    """Get the output directory from user."""
    while True:
        path = input("Output directory: ").strip().strip('"').strip("'")
        if not path:
            print("Using same directory as input file.")
            return None
        if not os.path.isdir(path):
            print(f"Error: directory not found: {path}")
            continue
        return os.path.abspath(path)


def get_output_format() -> str:
    """Get desired output format from user."""
    while True:
        choice = input("Output format [mid/ust/both] (default: both): ").strip().lower()
        if not choice:
            return 'both'
        if choice in ('mid', 'midi'):
            return 'mid'
        if choice in ('ust',):
            return 'ust'
        if choice in ('both', 'all'):
            return 'both'
        print("Invalid choice. Enter 'mid', 'ust', or 'both'.")


def main():
    print_banner()

    input_path = get_input_path()

    print(f"\nReading file: {input_path}")
    try:
        fmt = detect_format(input_path)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    print(f"Detected format: {fmt.upper()}")

    try:
        data = parse_file(input_path)
    except Exception as e:
        print(f"Error parsing file: {e}")
        sys.exit(1)

    note_count = len(data['notes'])
    bpm = data['bpm']
    name = data['project_name']
    print(f"Project: {name}")
    print(f"BPM: {bpm}")
    print(f"Notes: {note_count}")

    if note_count == 0:
        print("Warning: no notes found in file!")
        sys.exit(1)

    print("\nFirst 5 notes:")
    for n in data['notes'][:5]:
        print(f"  [{n['start_tick']:>6}] {midi_note_to_name(n['pitch']):>4}  {n['lyric']}  "
              f"({n['duration_ticks']} ticks)")

    print()
    output_dir = get_output_dir()
    output_format = get_output_format()

    if output_dir is None:
        output_dir = os.path.dirname(input_path)

    base_name = os.path.splitext(os.path.basename(input_path))[0]
    for suffix in [' - 副本']:
        if base_name.endswith(suffix):
            base_name = base_name[:-len(suffix)]

    print(f"\nOutput directory: {output_dir}")
    print()

    if output_format in ('mid', 'both'):
        mid_filename = f"{base_name}.mid"
        mid_path = os.path.join(output_dir, mid_filename)
        try:
            midi_data = build_midi(
                notes=data['notes'],
                bpm=data['bpm'],
                project_name=data['project_name'],
                resolution=data['resolution'],
                time_numerator=data['time_numerator'],
                time_denominator=data['time_denominator'],
            )
            with open(mid_path, 'wb') as f:
                f.write(midi_data)
            file_size = len(midi_data)
            print(f"  [OK] {mid_filename} ({file_size} bytes)")
        except Exception as e:
            print(f"  [FAIL] MIDI generation failed: {e}")

    if output_format in ('ust', 'both'):
        ust_filename = f"{base_name}.ust"
        ust_path = os.path.join(output_dir, ust_filename)
        try:
            ust_data = build_ust(
                notes=data['notes'],
                bpm=data['bpm'],
                project_name=data['project_name'],
                resolution=data['resolution'],
            )
            with open(ust_path, 'w', encoding='utf-8') as f:
                f.write(ust_data)
            file_size = len(ust_data.encode('utf-8'))
            print(f"  [OK] {ust_filename} ({file_size} bytes)")
        except Exception as e:
            print(f"  [FAIL] UST generation failed: {e}")

    print()
    print("Done!")


if __name__ == '__main__':
    main()