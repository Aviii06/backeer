from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


def now_iso(tz: ZoneInfo | None = None) -> str:
    return datetime.now(tz or ZoneInfo("Asia/Kolkata")).isoformat(timespec="seconds")


@dataclass
class EventWriter:
    job_id: str
    run_dir: Path
    timezone: str = "Asia/Kolkata"
    events_path: Path = field(init=False)
    commands_path: Path = field(init=False)
    _tz: ZoneInfo = field(init=False)

    def __post_init__(self) -> None:
        self.events_path = self.run_dir / "events.jsonl"
        self.commands_path = self.run_dir / "commands.jsonl"
        self._tz = ZoneInfo(self.timezone)

    def event(
        self,
        stage: str,
        event_type: str,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "ts": now_iso(self._tz),
            "job_id": self.job_id,
            "stage": stage,
            "type": event_type,
            "message": message,
            "data": data or {},
        }
        self._append_jsonl(self.events_path, payload)
        self._log_to_prefect(stage, event_type, message, data or {})
        print(f"[{stage}] {message}", flush=True)

    def command(self, stage: str, argv: list[str], cwd: Path | None = None) -> None:
        self._append_jsonl(
            self.commands_path,
            {
                "ts": now_iso(self._tz),
                "job_id": self.job_id,
                "stage": stage,
                "cwd": str(cwd) if cwd else None,
                "argv": argv,
            },
        )

    @staticmethod
    def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    @staticmethod
    def _log_to_prefect(
        stage: str,
        event_type: str,
        message: str,
        data: dict[str, Any],
    ) -> None:
        try:
            from prefect.logging import get_run_logger

            logger = get_run_logger()
        except Exception:
            return

        if data:
            logger.info("%s %s: %s %s", stage, event_type, message, data)
        else:
            logger.info("%s %s: %s", stage, event_type, message)
