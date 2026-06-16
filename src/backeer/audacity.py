from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from .events import EventWriter


IMPORT_ORDER = ("vocals.wav", "guitar.wav", "piano.wav", "bass.wav", "drums.wav", "other.wav")


def prepare_audacity_folder(
    *,
    stem_paths: dict[str, Path],
    audacity_dir: Path,
    events: EventWriter,
) -> list[Path]:
    events.event("audacity", "prepare.started", "preparing Audacity import folder")
    audacity_dir.mkdir(parents=True, exist_ok=True)

    imported: list[Path] = []
    for stem_name in IMPORT_ORDER:
        source = stem_paths.get(stem_name)
        if source is None:
            continue
        target = audacity_dir / stem_name
        if target.exists() or target.is_symlink():
            target.unlink()
        # Use an absolute/resolved path for the symlink target so the link doesn't
        # break if the current working directory changes later.
        try:
            resolved_source = source.resolve(strict=False)
        except Exception:
            resolved_source = source
        try:
            target.symlink_to(resolved_source)
        except OSError:
            # If symlink creation fails (e.g. on filesystems that disallow symlinks),
            # fall back to copying. If copy fails, emit an event and raise.
            try:
                shutil.copy2(source, target)
            except Exception as exc:
                events.event(
                    "audacity",
                    "prepare.failed",
                    "failed to create audacity import file",
                    {"source": str(source), "target": str(target), "error": str(exc)},
                )
                raise
        # Verify the target exists; fail early so we don't try to open missing files in Audacity.
        if not target.exists():
            events.event(
                "audacity",
                "prepare.failed",
                "audacity import file missing after create",
                {"target": str(target)},
            )
            raise RuntimeError(f"Failed to create audacity import file: {target}")
        imported.append(target)

    manifest = audacity_dir / "import_order.txt"
    manifest.write_text(
        "\n".join(str(path) for path in imported) + "\n",
        encoding="utf-8",
    )
    events.event(
        "audacity",
        "prepare.completed",
        "Audacity import folder is ready",
        {"files": [str(path) for path in imported]},
    )
    return imported


def _pipes_for_uid(uid: int) -> tuple[Path, Path]:
    return (
        Path(f"/tmp/audacity_script_pipe.to.{uid}"),
        Path(f"/tmp/audacity_script_pipe.from.{uid}"),
    )


def _start_audacity_app() -> bool:
    """Try to start the Audacity application (without opening files).

    Returns True if a start command was issued, False otherwise.
    """
    if sys.platform == "darwin":
        # Try direct executable path first (more reliable than 'open -a')
        direct_path = "/Applications/Audacity.app/Contents/MacOS/Audacity"
        if Path(direct_path).exists():
            cmd = [direct_path]
        else:
            cmd = ["open", "-a", "Audacity"]
    else:
        audacity_bin = shutil.which("audacity")
        if audacity_bin is not None:
            cmd = [audacity_bin]
        elif sys.platform.startswith("win"):
            cmd = ["cmd", "/c", "start", "Audacity"]
        else:
            # We don't have a reliable portable way to start Audacity on every
            # Linux distribution; bail out so we don't try to call xdg-open on a
            # non-existent file and confuse users.
            return False

    try:
        # Start Audacity detached so we don't block. Suppress output.
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def _find_any_pipes() -> tuple[Path, Path] | None:
    """Scan /tmp for any audacity script pipe pairs and return the first match.

    This helps in situations where the Audacity instance created pipes for a
    different UID (for example when a GUI was started by a different user) —
    it's reasonable to attempt to use any existing pipe pair before giving up.
    """
    tmp = Path("/tmp")
    candidates = sorted(tmp.glob("audacity_script_pipe.to.*"))
    for to in candidates:
        suffix = to.name.rsplit('.', 1)[-1]
        fromp = tmp / f"audacity_script_pipe.from.{suffix}"
        if fromp.exists():
            return (to, fromp)
    return None


def open_in_audacity(paths: list[Path], events: EventWriter, skip_pipe: bool = False) -> None:
    """Import stems into a single Audacity project.

    This function prefers the mod-script-pipe (if available). If the pipe is
    not present it will attempt to start Audacity (without passing files) and
    wait briefly for the pipes to appear. If pipes become available the stems
    are imported into the running Audacity instance. If pipes are not
    available the function falls back to opening files directly with Audacity.
    
    Args:
        paths: List of audio file paths to open
        events: EventWriter for logging
        skip_pipe: If True, skip pipe attempts and go directly to file opening
    """
    if not paths:
        events.event("audacity", "open.skipped", "no stems available to open in Audacity")
        return

    events.event(
        "audacity",
        "open.started",
        "opening stems in Audacity",
        {"files": [str(path) for path in paths]},
    )

    uid = os.getuid()
    pipe_to, pipe_from = _pipes_for_uid(uid)

    # If the pipes for the current UID aren't present, try to find any existing
    # pipe pair in /tmp and use that instead.
    if not (pipe_to.exists() and pipe_from.exists()):
        found = _find_any_pipes()
        if found is not None:
            pipe_to, pipe_from = found
            events.event(
                "audacity",
                "pipe.found",
                "found audacity script pipe for different UID; attempting to use it",
                {"to": str(pipe_to), "from": str(pipe_from)},
            )

    def _send_via_pipe():
        import time
        import select
        import fcntl

        try:
            # Open the "to" pipe with a timeout by setting it non-blocking
            try:
                to_fd = os.open(str(pipe_to), os.O_WRONLY | os.O_NONBLOCK)
            except BlockingIOError:
                # Pipe exists but no reader (Audacity not listening)
                events.event(
                    "audacity",
                    "pipe.blocked",
                    "audacity pipe exists but no reader (Audacity may not be listening)",
                    {"to": str(pipe_to)},
                )
                return False
            except Exception as exc:
                events.event(
                    "audacity",
                    "pipe.failed",
                    "failed to open Audacity pipe for writing",
                    {"error": str(exc)},
                )
                return False

            try:
                # Send absolute paths so Audacity can resolve them regardless of
                # Audacity's working directory.
                for path in paths:
                    try:
                        path_arg = str(path.resolve())
                    except Exception:
                        # Fall back to the path string if resolution fails.
                        path_arg = str(path)
                    cmd = f'Import2: Filename="{path_arg}"\n'
                    try:
                        os.write(to_fd, cmd.encode("utf-8"))
                    except BlockingIOError:
                        # Pipe buffer full; Audacity not consuming
                        events.event(
                            "audacity",
                            "pipe.blocked",
                            "audacity pipe buffer full (Audacity not consuming)",
                        )
                        return False
                    # Give Audacity a tiny moment to start processing each command.
                    time.sleep(1.5)

                events.event(
                    "audacity",
                    "pipe.completed",
                    "sent import commands to Audacity",
                    {"files": [str(p.resolve()) if p.exists() else str(p) for p in paths]},
                )

                # Attempt to read any responses Audacity wrote to the "from" pipe so
                # we can surface errors (non-blocking and with a short timeout).
                try:
                    fd = os.open(str(pipe_from), os.O_RDONLY | os.O_NONBLOCK)
                except Exception as exc:
                    events.event(
                        "audacity",
                        "pipe.read_unavailable",
                        "could not open audacity response pipe for reading",
                        {"error": str(exc)},
                    )
                    return True

                try:
                    responses: list[str] = []
                    deadline = time.time() + 2.0
                    while time.time() < deadline:
                        rlist, _, _ = select.select([fd], [], [], 0.25)
                        if fd in rlist:
                            try:
                                chunk = os.read(fd, 4096)
                            except BlockingIOError:
                                continue
                            if not chunk:
                                break
                            responses.append(chunk.decode("utf-8", errors="replace"))
                        else:
                            # No data available right now; continue waiting until deadline.
                            continue

                    if responses:
                        events.event(
                            "audacity",
                            "pipe.response",
                            "audacity script-pipe responses",
                            {"output": "".join(responses)},
                        )
                finally:
                    try:
                        os.close(fd)
                    except Exception:
                        pass

                return True
            finally:
                try:
                    os.close(to_fd)
                except Exception:
                    pass
        except Exception as exc:
            events.event(
                "audacity",
                "pipe.failed",
                "failed to write commands to Audacity pipe",
                {"error": str(exc)},
            )
            return False

    # If the pipes already exist and we're not skipping them, use them immediately.
    if not skip_pipe and pipe_to.exists() and pipe_from.exists():
        events.event("audacity", "pipe.started", "importing stems through Audacity pipe")
        if _send_via_pipe():
            events.event("audacity", "open.completed", "sent stems to Audacity")
        return

    # Pipes were not present or skipped. Attempt to start Audacity so it can create the
    # pipes (this only helps if the mod-script-pipe module is enabled in
    # Audacity preferences).
    if not skip_pipe:
        started = _start_audacity_app()
        if started:
            # Wait briefly for Audacity to start and create the pipes.
            import time

            deadline = time.time() + 3.0
            while time.time() < deadline:
                if pipe_to.exists() and pipe_from.exists():
                    events.event(
                        "audacity",
                        "pipe.started",
                        "audacity started and script pipe became available",
                    )
                    if _send_via_pipe():
                        events.event("audacity", "open.completed", "sent stems to Audacity")
                    return
                time.sleep(0.1)

    # If we reach this point the pipes are not available. Fall back to opening
    # files directly with Audacity (they'll open in separate windows/tabs).
    events.event(
        "audacity",
        "pipe.unavailable",
        "Audacity script pipe not available; falling back to direct file opening",
        {"to": str(pipe_to), "from": str(pipe_from)},
    )
    
    try:
        cmd = audacity_open_command(paths)
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        events.event(
            "audacity",
            "open.completed",
            "opened files directly in Audacity",
            {"command": " ".join(cmd)},
        )
    except Exception as exc:
        events.event(
            "audacity",
            "open.failed",
            "failed to open Audacity directly",
            {"error": str(exc)},
        )


def audacity_open_command(paths: list[Path]) -> list[str]:
    path_args = [str(path) for path in paths]
    if sys.platform == "darwin":
        # Use direct executable path instead of 'open -a' for better reliability
        direct_path = "/Applications/Audacity.app/Contents/MacOS/Audacity"
        if Path(direct_path).exists():
            return [direct_path, *path_args]
        return ["open", "-a", "Audacity", *path_args]

    audacity_bin = shutil.which("audacity")
    if audacity_bin is not None:
        return [audacity_bin, *path_args]

    if sys.platform.startswith("win"):
        return ["cmd", "/c", "start", "", *path_args]

    return ["xdg-open", str(paths[0])]
