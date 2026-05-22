#!/usr/bin/env python3
"""Replay the audacity import step for an existing run.

Usage:
    python -m backeer.scripts.replay_audacity /path/to/run_dir
or (from repository root):
    python Backeer/scripts/replay_audacity.py runs/2026-...

This recreates the `audacity/` import folder (symlinks/copies) and then
attempts to import the stems into a running Audacity via mod-script-pipe.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from backeer.events import EventWriter
from backeer.audacity import prepare_audacity_folder, open_in_audacity


def main(argv: list[str] | None = None) -> int:
    argv = list(argv) if argv is not None else sys.argv[1:]
    if not argv:
        print("Usage: replay_audacity.py /path/to/run_dir")
        return 2

    run_dir = Path(argv[0])
    if not run_dir.exists():
        print(f"Run directory does not exist: {run_dir}")
        return 2

    job_path = run_dir / "job.json"
    if not job_path.exists():
        print(f"job.json not found in run dir: {job_path}")
        return 2

    job = json.loads(job_path.read_text(encoding="utf-8"))
    stem_paths = {name: Path(p) for name, p in job.get("stem_paths", {}).items()}

    events = EventWriter(job["job_id"], run_dir)

    audacity_paths = prepare_audacity_folder(
        stem_paths=stem_paths, audacity_dir=run_dir / "audacity", events=events
    )

    open_in_audacity(audacity_paths, events)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
