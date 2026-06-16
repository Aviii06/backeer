from pathlib import Path

from backeer.audacity import (
    audacity_open_command,
    prepare_audacity_folder,
    _write_lof_file,
)
from backeer.events import EventWriter


def test_prepare_audacity_folder_creates_symlinks(tmp_path: Path) -> None:
    stem_dir = tmp_path / "stems"
    stem_dir.mkdir()
    for name in ("vocals.wav", "bass.wav", "drums.wav", "other.wav"):
        (stem_dir / name).write_bytes(b"fake wav data")

    stem_paths = {name: stem_dir / name for name in ("vocals.wav", "bass.wav", "drums.wav", "other.wav")}
    audacity_dir = tmp_path / "audacity"

    events = EventWriter("test-job", tmp_path)
    imported = prepare_audacity_folder(
        stem_paths=stem_paths,
        audacity_dir=audacity_dir,
        events=events,
        import_order=("vocals.wav", "bass.wav", "drums.wav", "other.wav"),
    )

    assert len(imported) == 4
    assert (audacity_dir / "vocals.wav").exists()
    assert (audacity_dir / "bass.wav").exists()
    assert (audacity_dir / "drums.wav").exists()
    assert (audacity_dir / "other.wav").exists()


def test_prepare_audacity_folder_respects_import_order(tmp_path: Path) -> None:
    stem_dir = tmp_path / "stems"
    stem_dir.mkdir()
    names = ("drums.wav", "vocals.wav", "bass.wav")
    for name in names:
        (stem_dir / name).write_bytes(b"fake wav data")

    stem_paths = {name: stem_dir / name for name in names}
    audacity_dir = tmp_path / "audacity"

    events = EventWriter("test-job", tmp_path)
    imported = prepare_audacity_folder(
        stem_paths=stem_paths,
        audacity_dir=audacity_dir,
        events=events,
        import_order=("drums.wav", "vocals.wav", "bass.wav"),
    )

    assert [p.name for p in imported] == ["drums.wav", "vocals.wav", "bass.wav"]

    manifest = (audacity_dir / "import_order.txt").read_text().strip().split("\n")
    assert manifest[0].endswith("drums.wav")
    assert manifest[1].endswith("vocals.wav")
    assert manifest[2].endswith("bass.wav")


def test_prepare_audacity_folder_missing_stem_skipped(tmp_path: Path) -> None:
    stem_dir = tmp_path / "stems"
    stem_dir.mkdir()
    (stem_dir / "vocals.wav").write_bytes(b"fake wav data")

    stem_paths = {"vocals.wav": stem_dir / "vocals.wav"}
    audacity_dir = tmp_path / "audacity"

    events = EventWriter("test-job", tmp_path)
    imported = prepare_audacity_folder(
        stem_paths=stem_paths,
        audacity_dir=audacity_dir,
        events=events,
        import_order=("vocals.wav", "bass.wav", "drums.wav"),
    )

    assert len(imported) == 1
    assert imported[0].name == "vocals.wav"


def test_prepare_audacity_folder_default_import_order(tmp_path: Path) -> None:
    stem_dir = tmp_path / "stems"
    stem_dir.mkdir()
    (stem_dir / "extra.wav").write_bytes(b"data")
    (stem_dir / "vocals.wav").write_bytes(b"data")

    stem_paths = {"extra.wav": stem_dir / "extra.wav", "vocals.wav": stem_dir / "vocals.wav"}
    audacity_dir = tmp_path / "audacity"

    events = EventWriter("test-job", tmp_path)
    imported = prepare_audacity_folder(
        stem_paths=stem_paths,
        audacity_dir=audacity_dir,
        events=events,
        import_order=None,
    )

    assert len(imported) == 2


def test_write_lof_file_format(tmp_path: Path) -> None:
    a = tmp_path / "a.wav"
    b = tmp_path / "b.wav"
    a.write_bytes(b"a")
    b.write_bytes(b"b")
    lof = _write_lof_file([a, b])
    content = lof.read_text()
    assert f'file "{a.resolve()}" offset 0' in content
    assert f'file "{b.resolve()}" offset 0' in content


def test_audacity_open_command_macos_direct_path(monkeypatch) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    direct_path = "/Applications/Audacity.app/Contents/MacOS/Audacity"

    real_exists = Path.exists

    def fake_exists(self):
        if str(self) == direct_path:
            return True
        return real_exists(self)

    monkeypatch.setattr(Path, "exists", fake_exists)

    cmd = audacity_open_command([Path("vocals.wav")])
    assert cmd[0] == direct_path
    assert "vocals.wav" in cmd


def test_audacity_open_command_linux_binary(monkeypatch) -> None:
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr("shutil.which", lambda x: "/usr/bin/audacity" if x == "audacity" else None)

    cmd = audacity_open_command([Path("vocals.wav"), Path("drums.wav")])
    assert cmd[0] == "/usr/bin/audacity"
    assert cmd[1:] == ["vocals.wav", "drums.wav"]


def test_audacity_open_command_windows(monkeypatch) -> None:
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setattr("shutil.which", lambda x: None)

    cmd = audacity_open_command([Path("vocals.wav")])
    assert cmd == ["cmd", "/c", "start", "", "vocals.wav"]


def test_audacity_open_command_linux_xdg_open_fallback(monkeypatch) -> None:
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr("shutil.which", lambda x: None)

    cmd = audacity_open_command([Path("vocals.wav")])
    assert cmd[0] == "xdg-open"
