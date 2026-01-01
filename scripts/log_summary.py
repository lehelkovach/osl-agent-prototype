#!/usr/bin/env python3
"""
Summarize agent logs for quick diagnosis.

Usage:
  python scripts/log_summary.py [--lines 200]

Environment:
  AGENT_LOG_FILE (default: ./log_dump.txt)
  SNAPDIR (default: ./log_snapshots)
"""

import argparse
import os
import re
from pathlib import Path


def read_tail(path: Path, lines: int) -> list[str]:
    if not path.exists():
        return []
    with path.open("r", errors="ignore") as f:
        data = f.readlines()
    return data[-lines:]


def last_snapshot(snapdir: Path) -> Path | None:
    if not snapdir.exists():
        return None
    snaps = sorted(snapdir.glob("error_*.log"))
    return snaps[-1] if snaps else None


def extract_errors(lines: list[str], max_blocks: int = 3) -> list[list[str]]:
    blocks = []
    current: list[str] = []
    pattern = re.compile(r"(ERROR|Exception|Traceback)")
    for line in lines:
        if pattern.search(line):
            current.append(line)
        elif current:
            current.append(line)
            if line.strip() == "":
                blocks.append(current)
                current = []
                if len(blocks) >= max_blocks:
                    break
    if current and len(blocks) < max_blocks:
        blocks.append(current)
    return blocks


def main():
    parser = argparse.ArgumentParser(description="Summarize agent logs.")
    parser.add_argument("--lines", type=int, default=200, help="tail this many lines from log")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    log_path = Path(os.environ.get("AGENT_LOG_FILE", root / "log_dump.txt"))
    snapdir = Path(os.environ.get("SNAPDIR", root / "log_snapshots"))

    print(f"Log file: {log_path}")
    if log_path.exists():
        tail = read_tail(log_path, args.lines)
        print(f"\n== Last {min(args.lines, len(tail))} lines ==")
        print("".join(tail))
        errors = extract_errors(tail)
        if errors:
            print("\n== Detected error snippets ==")
            for i, block in enumerate(errors, 1):
                print(f"-- Error block {i} --")
                print("".join(block).rstrip())
        else:
            print("\nNo error patterns detected in tail.")
    else:
        print("Log file not found.")

    snap = last_snapshot(snapdir)
    if snap:
        print(f"\nLatest snapshot: {snap}")
        snap_tail = read_tail(snap, args.lines)
        print(f"== Snapshot tail ({min(args.lines, len(snap_tail))} lines) ==")
        print("".join(snap_tail))
    else:
        print("\nNo snapshots found.")


if __name__ == "__main__":
    main()
