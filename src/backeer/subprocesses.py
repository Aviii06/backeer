from __future__ import annotations

import subprocess
from pathlib import Path

from .events import EventWriter


class CommandError(RuntimeError):
    def __init__(self, stage: str, argv: list[str], returncode: int, log_path: Path):
        self.stage = stage
        self.argv = argv
        self.returncode = returncode
        self.log_path = log_path
        super().__init__(
            f"{stage} failed with exit code {returncode}; see {log_path}"
        )


def run_streamed(
    *,
    stage: str,
    argv: list[str],
    log_path: Path,
    events: EventWriter,
    cwd: Path | None = None,
) -> None:
    events.command(stage, argv, cwd)
    events.event(stage, "command.started", "started command", {"argv": argv})
    log_path.parent.mkdir(parents=True, exist_ok=True)

    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            argv,
            cwd=str(cwd) if cwd else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            clean = line.rstrip()
            log.write(line)
            log.flush()
            if clean:
                events.event(stage, "command.output", clean)

        returncode = process.wait()

    if returncode != 0:
        events.event(
            stage,
            "command.failed",
            "command failed",
            {"returncode": returncode, "log_path": str(log_path)},
        )
        raise CommandError(stage, argv, returncode, log_path)

    events.event(stage, "command.completed", "completed command")
