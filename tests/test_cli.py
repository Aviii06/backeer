import pytest
from pathlib import Path

from backeer.cli import build_parser, main


def test_replay_rejects_url() -> None:
    with pytest.raises(SystemExit):
        main(["--replay", "runs/some-run", "https://example.com/video"])


def test_replay_rejects_prefect() -> None:
    with pytest.raises(SystemExit):
        main(["--replay", "runs/some-run", "--prefect"])


def test_missing_url_error() -> None:
    with pytest.raises(SystemExit):
        main([])


def test_config_flag_accepted() -> None:
    args = build_parser().parse_args(
        ["https://example.com/video", "--config", "my-config.toml"]
    )
    assert args.config == Path("my-config.toml")


def test_model_choices_only_known() -> None:
    args = build_parser().parse_args(
        ["https://example.com/video", "--model", "htdemucs"]
    )
    assert args.model == "htdemucs"


def test_model_choices_rejects_unknown() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(
            ["https://example.com/video", "--model", "nonexistent"]
        )


def test_prefect_api_url_without_prefect_rejected() -> None:
    with pytest.raises(SystemExit):
        main(["--prefect-api-url", "http://x/api", "https://example.com/video"])
