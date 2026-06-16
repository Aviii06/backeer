from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path


EXPECTED_STEMS_6S = (
    "bass.wav",
    "drums.wav",
    "guitar.wav",
    "other.wav",
    "piano.wav",
    "vocals.wav",
)


@dataclass
class WorkflowConfig:
    url: str
    name: str | None = None
    runs_dir: Path = Path("runs")
    model: str = "htdemucs_6s"
    expected_stems: tuple[str, ...] = EXPECTED_STEMS_6S
    with_audacity: bool = False


@dataclass
class JobState:
    job_id: str
    run_dir: Path
    config: WorkflowConfig
    status: str = "created"
    source_audio: Path | None = None
    normalized_audio: Path | None = None
    demucs_output_dir: Path | None = None
    stem_paths: dict[str, Path] = field(default_factory=dict)

    def to_jsonable(self) -> dict:
        payload = asdict(self)
        payload["run_dir"] = str(self.run_dir)
        payload["config"]["runs_dir"] = str(self.config.runs_dir)
        payload["source_audio"] = str(self.source_audio) if self.source_audio else None
        payload["normalized_audio"] = (
            str(self.normalized_audio) if self.normalized_audio else None
        )
        payload["demucs_output_dir"] = (
            str(self.demucs_output_dir) if self.demucs_output_dir else None
        )
        payload["stem_paths"] = {
            name: str(path) for name, path in self.stem_paths.items()
        }
        return payload
