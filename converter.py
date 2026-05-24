# -*- coding: utf-8 -*-
"""
DSC and UFDATA format parser.

DSC format: Chinese-keyed JSON with detailed phoneme data.
  - 音高: continuous pitch (float, semitone-based, ~C3 = 48 ish, but varies)
  - 时长: duration in beats (float)
  - 音节发音.原文: display text (lyric character)
  - 音节发音.核心元音: core vowel
  - 声乐曲[i].速度: BPM

UFDATA format: English-keyed JSON, simpler structure.
  - key: MIDI note number (integer)
  - tickOn/tickOff: tick positions (integer)
  - lyric: display text
  - pitch: pitch bend data (optional)
  - tempos[].bpm: BPM
"""

import json
from typing import List, Optional


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

    # Extract tempo
    tempos = project.get('tempos', [])
    if tempos:
        bpm = tempos[0].get('bpm', 120.0)

    # Extract time signature
    ts_list = project.get('timeSignatures', [])
    if ts_list:
        time_num = ts_list[0].get('numerator', 4)
        time_den = ts_list[0].get('denominator', 4)

    project_name = project.get('name', 'Untitled')

    # Extract notes from all tracks
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

    # Extract time signature from top-level 拍号
    ts = data.get('拍号', {})
    if isinstance(ts, dict):
        time_num = ts.get('分子', 4)
        time_den = ts.get('分母', 4)

    # Extract BPM from vocal tracks (field: 每分钟拍数)
    vocal_tracks = data.get('声乐曲', [])
    if vocal_tracks:
        first_track = vocal_tracks[0]
        track_bpm = first_track.get('每分钟拍数', None)
        if track_bpm is not None:
            bpm = float(track_bpm)

    # Extract notes
    notes = []
    current_tick = 0

    for track in vocal_tracks:
        track_notes = track.get('音符', [])

        for note in track_notes:
            # Skip rest notes
            pronunciation = note.get('音节发音', {})
            is_rest = pronunciation.get('休止符', False)
            if is_rest:
                duration_beats = note.get('时长', 0.5)
                current_tick += int(duration_beats * resolution)
                continue

            # Pitch: DSC uses continuous semitone values
            # C4 = 60 in MIDI standard, DSC seems to use similar but might differ
            # From the sample: "关" has 音高=56.73 which maps to key=57 in UFDATA (A3)
            # So DSC pitch is approximately MIDI note number
            raw_pitch = note.get('音高', 60.0)
            midi_pitch = int(round(raw_pitch))

            # Duration in beats
            duration_beats = note.get('时长', 0.5)
            duration_ticks = max(1, int(duration_beats * resolution))

            # Lyric text
            lyric_text = pronunciation.get('原文', '')
            display_text = pronunciation.get('音符显示', lyric_text)

            # Use the lyric character for UTAU
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

    # Check for UFDATA format (English keys)
    if 'formatVersion' in data:
        return 'ufdata'

    # Check for DSC format (Chinese keys)
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
