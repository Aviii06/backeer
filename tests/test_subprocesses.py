from pathlib import Path

from backeer.subprocesses import CommandError


def test_command_error_contains_stage_and_log() -> None:
    log_path = Path("/tmp/test.log")
    err = CommandError(
        stage="demucs",
        argv=["python", "-m", "demucs"],
        returncode=1,
        log_path=log_path,
    )
    assert err.stage == "demucs"
    assert err.returncode == 1
    assert err.log_path == log_path
    assert "demucs" in str(err)
    assert "exit code 1" in str(err)
