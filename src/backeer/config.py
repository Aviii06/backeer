from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class BackeerConfig:
    model: str = "htdemucs_6s"
    runs_dir: Path = Path("runs")
    with_audacity: bool = False
    timezone: str = "Asia/Kolkata"


def find_config(start: Path | None = None) -> Path | None:
    current = (start or Path.cwd()).resolve()
    for ancestor in [current, *current.parents]:
        candidate = ancestor / "backeer.toml"
        if candidate.is_file():
            return candidate
    return None


def load_config(path: Path | None = None) -> BackeerConfig:
    config = BackeerConfig()
    filepath = path or find_config()
    if filepath is None or not filepath.is_file():
        return config

    with filepath.open("rb") as f:
        data = tomllib.load(f)

    backeer = data.get("backeer", {})
    if "model" in backeer:
        config.model = backeer["model"]
    if "runs-dir" in backeer:
        config.runs_dir = Path(backeer["runs-dir"]).expanduser().resolve()
    if "with-audacity" in backeer:
        config.with_audacity = backeer["with-audacity"]
    if "timezone" in backeer:
        config.timezone = backeer["timezone"]

    return config
