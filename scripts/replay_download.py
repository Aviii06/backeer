#!/usr/bin/env python3
"""Replay just the download step for an existing run.

Usage:
    python Backeer/scripts/replay_download.py /path/to/run_dir

This will read the run's job.json (to get the original URL and config),
recreate the logs directory if necessary, and call the same download_audio
function used by Backeer so logs go to the same log file.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from backeer.events import EventWriter
from backeer.models import JobState, WorkflowConfig
from backeer.workflow import download_audio


def main(argv: list[str] | None = None) -> int:
    argv = list(argv) if argv is not None else sys.argv[1:]
    if not argv:
        print("Usage: replay_download.py /path/to/run_dir")
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
    cfg = job.get("config", {})
    url = cfg.get("url")
    if not url:
        print("No URL found in job.json config")
        return 2

    config = WorkflowConfig(
        url=url,
        name=cfg.get("name"),
        runs_dir=Path(cfg.get("runs_dir", "runs")),
        model=cfg.get("model", "htdemucs_6s"),
        audacity_pipe=cfg.get("audacity_pipe", False),
        open_audacity=cfg.get("open_audacity", False),
    )

    state = JobState(job_id=job.get("job_id", "replay"), run_dir=run_dir, config=config)
    events = EventWriter(state.job_id, run_dir)

    # Ensure logs dir exists
    (run_dir / "logs").mkdir(parents=True, exist_ok=True)

    try:
        source = download_audio(state, events)
        print(f"Download completed, source audio: {source}")
        return 0
    except Exception as exc:
        print(f"Download failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
