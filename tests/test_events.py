import json
from pathlib import Path
from datetime import datetime

from backeer.events import EventWriter, now_iso
from zoneinfo import ZoneInfo


def test_event_writer_appends_jsonl(tmp_path: Path) -> None:
    events = EventWriter("job-1", tmp_path)
    events.event("download", "started", "starting download", {"url": "https://x"})

    lines = (tmp_path / "events.jsonl").read_text().strip().split("\n")
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["job_id"] == "job-1"
    assert data["stage"] == "download"
    assert data["type"] == "started"
    assert data["message"] == "starting download"
    assert data["data"]["url"] == "https://x"


def test_event_writer_multiple_events_append(tmp_path: Path) -> None:
    events = EventWriter("job-1", tmp_path)
    events.event("step1", "type1", "msg1")
    events.event("step2", "type2", "msg2")
    events.event("step3", "type3", "msg3")

    lines = (tmp_path / "events.jsonl").read_text().strip().split("\n")
    assert len(lines) == 3
    data = [json.loads(line) for line in lines]
    assert [d["stage"] for d in data] == ["step1", "step2", "step3"]


def test_command_writer_serializes(tmp_path: Path) -> None:
    events = EventWriter("job-1", tmp_path)
    events.command("download", ["yt-dlp", "-f", "bestaudio", "https://x"], cwd=Path("/tmp"))

    lines = (tmp_path / "commands.jsonl").read_text().strip().split("\n")
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["job_id"] == "job-1"
    assert data["stage"] == "download"
    assert data["argv"] == ["yt-dlp", "-f", "bestaudio", "https://x"]
    assert data["cwd"] == "/tmp"


def test_command_writer_no_cwd(tmp_path: Path) -> None:
    events = EventWriter("job-1", tmp_path)
    events.command("normalize", ["ffmpeg", "-y", "-i", "x", "y"])

    lines = (tmp_path / "commands.jsonl").read_text().strip().split("\n")
    data = json.loads(lines[0])
    assert data["cwd"] is None


def test_now_iso_returns_string() -> None:
    ts = now_iso()
    assert isinstance(ts, str)
    assert "T" in ts


def test_now_iso_respects_timezone() -> None:
    ts_utc = now_iso(ZoneInfo("UTC"))
    ts_ist = now_iso(ZoneInfo("Asia/Kolkata"))
    assert ts_utc != ts_ist


def test_event_writer_respects_timezone(tmp_path: Path) -> None:
    events = EventWriter("job-1", tmp_path, timezone="UTC")
    events.event("test", "check", "timezone check")

    lines = (tmp_path / "events.jsonl").read_text().strip().split("\n")
    data = json.loads(lines[0])
    ts = datetime.fromisoformat(data["ts"])
    assert ts.tzinfo is not None


def test_events_path_created_in_run_dir(tmp_path: Path) -> None:
    events = EventWriter("job-1", tmp_path)
    assert events.events_path == tmp_path / "events.jsonl"
    assert events.commands_path == tmp_path / "commands.jsonl"
