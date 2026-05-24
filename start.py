# -*- coding: utf-8 -*-
"""
dashichang-to-UTAU - Convert Dashichang project files to UTAU formats.

Usage:
    python start.py

Supports:
    - DSC format (Chinese-keyed JSON)
    - UFDATA format (English-keyed JSON)

Output formats:
    - MID (Standard MIDI File, UTAU-compatible)
    - UST (UTAU Sequence Text)
"""

import os
import sys

from converter import parse_file, detect_format
from midi_writer import build_midi
from ust_writer import build_ust, midi_note_to_name


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


def get_output_dir() -> str:
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

    # Step 1: Get input file
    input_path = get_input_path()

    # Step 2: Detect and parse format
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

    # Show first few notes
    print("\nFirst 5 notes:")
    for n in data['notes'][:5]:
        print(f"  [{n['start_tick']:>6}] {midi_note_to_name(n['pitch']):>4}  {n['lyric']}  "
              f"({n['duration_ticks']} ticks)")

    # Step 3: Get output options
    print()
    output_dir = get_output_dir()
    output_format = get_output_format()

    if output_dir is None:
        output_dir = os.path.dirname(input_path)

    base_name = os.path.splitext(os.path.basename(input_path))[0]
    # Remove common suffixes
    for suffix in [' - 副本']:
        if base_name.endswith(suffix):
            base_name = base_name[:-len(suffix)]

    # Step 4: Generate output files
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
