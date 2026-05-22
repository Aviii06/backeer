from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .audacity import open_in_audacity, prepare_audacity_folder
from .events import EventWriter
from .models import JobState, WorkflowConfig
from .subprocesses import run_streamed


LOCAL_TZ = ZoneInfo("Asia/Kolkata")


def run_workflow(config: WorkflowConfig) -> JobState:
    require_tools()
    state = create_job(config)
    events = EventWriter(state.job_id, state.run_dir)

    try:
        write_job(state)
        events.event("job", "created", "created run folder", {"run_dir": str(state.run_dir)})
        state.status = "running"
        write_job(state)

        state.source_audio = download_audio(state, events)
        write_job(state)

        state.normalized_audio = normalize_audio(state, events)
        write_job(state)

        state.demucs_output_dir = separate_stems(state, events)
        write_job(state)

        state.stem_paths = validate_stems(state, events)
        write_job(state)

        audacity_paths = prepare_audacity_folder(
            stem_paths=state.stem_paths,
            audacity_dir=state.run_dir / "audacity",
            events=events,
        )
        if config.audacity_pipe or config.open_audacity:
            open_in_audacity(audacity_paths, events)

        state.status = "completed"
        write_job(state)
        events.event("job", "completed", "workflow completed successfully")
        return state
    except Exception as exc:
        state.status = "failed"
        write_job(state)
        events.event("job", "failed", str(exc), {"error_type": type(exc).__name__})
        raise


def require_tools() -> None:
    missing = [tool for tool in ("yt-dlp", "ffmpeg", "ffprobe") if shutil.which(tool) is None]
    if missing:
        raise RuntimeError(f"Missing required command-line tools: {', '.join(missing)}")

    demucs_check = subprocess.run(
        [sys.executable, "-c", "import demucs"],
        capture_output=True,
        text=True,
        check=False,
    )
    if demucs_check.returncode != 0:
        raise RuntimeError(
            "Missing Demucs for the active Python interpreter. "
            "Install it so this works: python -m demucs"
        )


def create_job(config: WorkflowConfig) -> JobState:
    job_id = uuid.uuid4().hex[:8]
    slug = slugify(config.name or "youtube-audio")
    stamp = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d_%H-%M-%S")
    run_dir = config.runs_dir / f"{stamp}_{slug}_{job_id}"

    for child in ("logs", "source", "normalized", "stems", "audacity", "debug"):
        (run_dir / child).mkdir(parents=True, exist_ok=True)

    return JobState(job_id=job_id, run_dir=run_dir, config=config)


def download_audio(state: JobState, events: EventWriter) -> Path:
    source_dir = state.run_dir / "source"
    argv = [
        "yt-dlp",
        "--no-playlist",
        "-f",
        "bestaudio",
        "-o",
        str(source_dir / "source.%(ext)s"),
        state.config.url,
    ]
    run_streamed(
        stage="download",
        argv=argv,
        log_path=state.run_dir / "logs" / "yt-dlp.log",
        events=events,
    )
    candidates = [path for path in source_dir.iterdir() if path.is_file()]
    if not candidates:
        raise RuntimeError("yt-dlp completed but no source audio file was found")
    source = max(candidates, key=lambda path: path.stat().st_mtime)
    events.event("download", "artifact", "downloaded source audio", {"path": str(source)})
    return source


def normalize_audio(state: JobState, events: EventWriter) -> Path:
    if state.source_audio is None:
        raise RuntimeError("Cannot normalize before source audio exists")

    output = state.run_dir / "normalized" / "input.wav"
    argv = [
        "ffmpeg",
        "-y",
        "-i",
        str(state.source_audio),
        "-vn",
        "-ac",
        "2",
        "-ar",
        "44100",
        str(output),
    ]
    run_streamed(
        stage="normalize",
        argv=argv,
        log_path=state.run_dir / "logs" / "ffmpeg-normalize.log",
        events=events,
    )
    probe_audio(output, state.run_dir / "debug" / "normalized.ffprobe.json", events)
    return output


def separate_stems(state: JobState, events: EventWriter) -> Path:
    if state.normalized_audio is None:
        raise RuntimeError("Cannot separate stems before normalized audio exists")

    output_root = state.run_dir / "stems"
    argv = [
        sys.executable,
        "-m",
        "demucs",
        "-n",
        state.config.model,
        "--out",
        str(output_root),
        str(state.normalized_audio),
    ]
    run_streamed(
        stage="demucs",
        argv=argv,
        log_path=state.run_dir / "logs" / "demucs.log",
        events=events,
    )
    demucs_dir = output_root / state.config.model / state.normalized_audio.stem
    if not demucs_dir.exists():
        matches = list(output_root.glob(f"{state.config.model}/**"))
        raise RuntimeError(
            f"Demucs completed but expected output folder was not found: {demucs_dir}; found {matches}"
        )
    events.event("demucs", "artifact", "created Demucs output folder", {"path": str(demucs_dir)})
    return demucs_dir


def validate_stems(state: JobState, events: EventWriter) -> dict[str, Path]:
    if state.demucs_output_dir is None:
        raise RuntimeError("Cannot validate before Demucs output exists")

    results: dict[str, dict[str, int | str | bool]] = {}
    stem_paths: dict[str, Path] = {}
    errors: list[str] = []

    for stem in state.config.expected_stems:
        path = state.demucs_output_dir / stem
        exists = path.exists()
        size = path.stat().st_size if exists else 0
        ok = exists and size > 0
        results[stem] = {"path": str(path), "exists": exists, "size": size, "ok": ok}
        if ok:
            stem_paths[stem] = path
        else:
            errors.append(stem)

    validation_path = state.run_dir / "validation.json"
    validation_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    if errors:
        events.event(
            "validate",
            "failed",
            "missing or empty expected stems",
            {"missing_or_empty": errors, "validation": str(validation_path)},
        )
        raise RuntimeError(f"Missing or empty expected stems: {', '.join(errors)}")

    events.event(
        "validate",
        "completed",
        "validated expected stems",
        {"stems": list(stem_paths), "validation": str(validation_path)},
    )
    return stem_paths


def probe_audio(audio_path: Path, output_path: Path, events: EventWriter) -> None:
    argv = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(audio_path),
    ]
    events.command("probe", argv)
    result = subprocess.run(argv, capture_output=True, text=True, check=False)
    output_path.write_text(result.stdout or result.stderr, encoding="utf-8")
    if result.returncode != 0:
        events.event("probe", "failed", "ffprobe failed", {"path": str(output_path)})
    else:
        events.event("probe", "completed", "wrote ffprobe metadata", {"path": str(output_path)})


def write_job(state: JobState) -> None:
    (state.run_dir / "job.json").write_text(
        json.dumps(state.to_jsonable(), indent=2),
        encoding="utf-8",
    )


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    return value[:60] or "youtube-audio"
