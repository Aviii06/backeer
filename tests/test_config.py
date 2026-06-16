from pathlib import Path

from backeer.config import BackeerConfig, find_config, load_config


def test_default_config_has_sensible_values() -> None:
    cfg = BackeerConfig()
    assert cfg.model == "htdemucs_6s"
    assert cfg.runs_dir == Path("runs")
    assert cfg.with_audacity is False
    assert cfg.timezone == "Asia/Kolkata"


def test_find_config_in_cwd(tmp_path: Path) -> None:
    cfg_file = tmp_path / "backeer.toml"
    cfg_file.write_text('[backeer]\nmodel = "htdemucs"\n')
    found = find_config(start=tmp_path)
    assert found == cfg_file


def test_find_config_in_parent(tmp_path: Path) -> None:
    cfg_file = tmp_path / "backeer.toml"
    cfg_file.write_text('[backeer]\nmodel = "htdemucs"\n')
    subdir = tmp_path / "sub" / "deep"
    subdir.mkdir(parents=True)
    found = find_config(start=subdir)
    assert found == cfg_file


def test_find_config_not_found(tmp_path: Path) -> None:
    found = find_config(start=tmp_path)
    assert found is None


def test_load_config_parses_all_fields(tmp_path: Path) -> None:
    cfg_file = tmp_path / "backeer.toml"
    cfg_file.write_text(
        '[backeer]\n'
        'model = "htdemucs"\n'
        'runs-dir = "~/my-runs"\n'
        'with-audacity = true\n'
        'timezone = "UTC"\n'
    )
    cfg = load_config(cfg_file)
    assert cfg.model == "htdemucs"
    assert str(cfg.runs_dir) == str(Path("~/my-runs").expanduser().resolve())
    assert cfg.with_audacity is True
    assert cfg.timezone == "UTC"


def test_load_config_partial_fields(tmp_path: Path) -> None:
    cfg_file = tmp_path / "backeer.toml"
    cfg_file.write_text('[backeer]\nmodel = "htdemucs"\n')
    cfg = load_config(cfg_file)
    assert cfg.model == "htdemucs"
    assert cfg.runs_dir == Path("runs")
    assert cfg.with_audacity is False
    assert cfg.timezone == "Asia/Kolkata"


def test_load_config_no_file_returns_defaults() -> None:
    cfg = load_config(Path("/nonexistent/backeer.toml"))
    assert cfg.model == "htdemucs_6s"


def test_load_config_finds_nearest_file() -> None:
    cfg = load_config()
    assert isinstance(cfg, BackeerConfig)


def test_load_config_empty_toml_returns_defaults(tmp_path: Path) -> None:
    cfg_file = tmp_path / "backeer.toml"
    cfg_file.write_text("")
    cfg = load_config(cfg_file)
    assert cfg.model == "htdemucs_6s"
