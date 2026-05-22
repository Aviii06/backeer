from __future__ import annotations

from pathlib import Path

from .audacity import open_in_audacity, prepare_audacity_folder
from .events import EventWriter
from .models import WorkflowConfig
from .workflow import (
    create_job,
    download_audio,
    normalize_audio,
    require_tools,
    separate_stems,
    validate_stems,
    write_job,
)

try:
    from prefect import flow, task
except ImportError:  # pragma: no cover
    flow = None
    task = None


if flow is not None:

    def mark_failed(state, exc: Exception) -> None:
        events = EventWriter(state.job_id, state.run_dir)
        state.status = "failed"
        write_job(state)
        events.event("job", "failed", str(exc), {"error_type": type(exc).__name__})

    @task
    def check_requirements() -> None:
        require_tools()

    @task
    def create_state(config: WorkflowConfig):
        state = create_job(config)
        events = EventWriter(state.job_id, state.run_dir)
        write_job(state)
        events.event("job", "created", "created run folder", {"run_dir": str(state.run_dir)})
        state.status = "running"
        write_job(state)
        return state

    @task
    def download_task(state):
        try:
            events = EventWriter(state.job_id, state.run_dir)
            state.source_audio = download_audio(state, events)
            write_job(state)
            return state
        except Exception as exc:
            mark_failed(state, exc)
            raise

    @task
    def normalize_task(state):
        try:
            events = EventWriter(state.job_id, state.run_dir)
            state.normalized_audio = normalize_audio(state, events)
            write_job(state)
            return state
        except Exception as exc:
            mark_failed(state, exc)
            raise

    @task
    def demucs_task(state):
        try:
            events = EventWriter(state.job_id, state.run_dir)
            state.demucs_output_dir = separate_stems(state, events)
            write_job(state)
            return state
        except Exception as exc:
            mark_failed(state, exc)
            raise

    @task
    def validate_task(state):
        try:
            events = EventWriter(state.job_id, state.run_dir)
            state.stem_paths = validate_stems(state, events)
            write_job(state)
            return state
        except Exception as exc:
            mark_failed(state, exc)
            raise

    @task
    def audacity_task(state):
        try:
            events = EventWriter(state.job_id, state.run_dir)
            audacity_paths = prepare_audacity_folder(
                stem_paths=state.stem_paths,
                audacity_dir=state.run_dir / "audacity",
                events=events,
            )
            if state.config.open_audacity:
                open_in_audacity(audacity_paths, events)
            state.status = "completed"
            write_job(state)
            events.event("job", "completed", "workflow completed successfully")
            return state
        except Exception as exc:
            mark_failed(state, exc)
            raise

    @flow(name="youtube-to-audacity-stems")
    def youtube_to_audacity_stems(
        url: str,
        name: str | None = None,
        runs_dir: str = "runs",
        model: str = "htdemucs_6s",
        audacity_pipe: bool = False,
        open_audacity: bool = False,
    ) -> str:
        config = WorkflowConfig(
            url=url,
            name=name,
            runs_dir=Path(runs_dir),
            model=model,
            audacity_pipe=audacity_pipe,
            open_audacity=open_audacity,
        )
        check_requirements()
        state = create_state(config)
        state = download_task(state)
        state = normalize_task(state)
        state = demucs_task(state)
        state = validate_task(state)
        state = audacity_task(state)
        return str(state.run_dir)

else:

    def youtube_to_audacity_stems(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("Prefect is not installed. Install with: pip install '.[orchestration]'")
