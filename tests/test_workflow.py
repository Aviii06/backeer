from pathlib import Path

from backeer.audacity import audacity_open_command
from backeer.cli import build_parser
from backeer.models import WorkflowConfig
from backeer.workflow import slugify, validate_stems
from backeer.models import JobState
from backeer.events import EventWriter


def test_slugify_keeps_names_filesystem_friendly() -> None:
    assert slugify(" My Song!! Guitar/Piano ") == "my-song-guitar-piano"


def test_validate_stems_accepts_htdemucs_6s_outputs(tmp_path: Path) -> None:
    stem_dir = tmp_path / "stems"
    stem_dir.mkdir()
    for name in WorkflowConfig(url="x").expected_stems:
        (stem_dir / name).write_bytes(b"wav")

    state = JobState(
        job_id="abc123",
        run_dir=tmp_path,
        config=WorkflowConfig(url="x"),
        demucs_output_dir=stem_dir,
    )
    paths = validate_stems(state, EventWriter("abc123", tmp_path))

    assert set(paths) == {
        "bass.wav",
        "drums.wav",
        "guitar.wav",
        "other.wav",
        "piano.wav",
        "vocals.wav",
    }


def test_cli_accepts_prefect_dashboard_options() -> None:
    args = build_parser().parse_args(
        [
            "https://example.com/video",
            "--prefect",
            "--prefect-api-url",
            "http://127.0.0.1:4200/api",
            "--detach",
            "--with-audacity",
        ]
    )

    assert args.prefect is True
    assert args.prefect_api_url == "http://127.0.0.1:4200/api"
    assert args.detach is True
    assert args.with_audacity is True


def test_audacity_open_command_uses_macos_app_launcher(monkeypatch) -> None:
    monkeypatch.setattr("sys.platform", "darwin")

    assert audacity_open_command([Path("vocals.wav"), Path("drums.wav")]) == [
        "open",
        "-a",
        "Audacity",
        "vocals.wav",
        "drums.wav",
    ]
