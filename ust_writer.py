# -*- coding: utf-8 -*-
"""
UST file writer for UTAU.

Generates standard UST (UTAU Sequence Text) files from parsed note data.
"""

from typing import List


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

    Returns:
        Complete UST file as string
    """
    if not notes:
        return "[#SETTINGS]\nTempo=120.00\nVoiceDir=\nOutfile=output.wav\nCacheDir=\nMode2=True\n"

    lines = []

    # Header
    lines.append("[#SETTINGS]")
    lines.append(f"Tempo={bpm:.2f}")
    lines.append(f"VoiceDir={voice_dir}")
    lines.append("Outfile=}")
    lines.append("CacheDir=")
    lines.append("Mode2=True")

    # Sort notes by start_tick
    sorted_notes = sorted(notes, key=lambda n: n['start_tick'])

    # Calculate tick-to-millisecond conversion
    # At given BPM, one quarter note = 60000/BPM ms
    # If 480 ticks per quarter note, then 1 tick = (60000/BPM)/480 ms
    ticks_per_qn = 480
    ms_per_tick = (60000.0 / bpm) / ticks_per_qn

    for i, note in enumerate(sorted_notes):
        duration_ticks = max(1, note['duration_ticks'])
        lyric = note.get('lyric', '-')

        # Skip rests (they're handled by negative duration gaps)
        if lyric == '-' or not lyric.strip():
            lyric = 'R'

        note_name = midi_note_to_name(note['pitch'])

        # Calculate preutterance and overlap (simplified defaults)
        pre_utt = 0.0
        overlap = 0.0

        # Duration in milliseconds
        duration_ms = duration_ticks * ms_per_tick

        # Left limit and right limit (simplified)
        length_ms = max(1, int(duration_ms))

        lines.append("")
        lines.append(f"[#{i:04d}]")
        lines.append(f"Lyric={lyric}")
        lines.append(f"Alias=")
        lines.append(f"Offset=0")
        lines.append(f"Consonant=0")
        lines.append(f"Cutoff=0")
        lines.append(f"PreUtterance=")
        lines.append(f"VoiceOverlap=")
        lines.append("")
        lines.append(f"Envelope=0,5,0,100,100,0")
        lines.append("")
        lines.append(f"@f2={note_name}")
        lines.append(f"@p2={length_ms}")

    # Handle rests between notes (gaps)
    # UTAU handles this through the previous note's length

    return '\n'.join(lines) + '\n'
