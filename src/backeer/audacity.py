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


def open_in_audacity(
    paths: list[Path],
    events: EventWriter,
    project_name: str | None = None,
) -> None:
    """Open stems in a single Audacity project.

    Uses mod-script-pipe if available; falls back to a LOF (List of Files)
    manifest that opens all files in one project.

    Args:
        paths: List of audio file paths to open
        events: EventWriter for logging
        project_name: Optional name to assign to the new Audacity project
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
        import errno

        try:
            # Try to open the "to" pipe for writing with a timeout
            try:
                # Use O_NONBLOCK for open to prevent hanging if reader isn't ready
                time.sleep(1.5)  # Brief pause to increase chance that Audacity is ready for the pipe
                to_fd = os.open(str(pipe_to), os.O_WRONLY | os.O_NONBLOCK)
            except OSError as exc:
                if exc.errno in (errno.ENXIO, errno.ENOENT):
                    # Pipe doesn't exist or no reader
                    events.event(
                        "audacity",
                        "pipe.failed",
                        "Audacity pipe not ready (Audacity may not have mod-script-pipe enabled)",
                        {"error": str(exc), "to": str(pipe_to)},
                    )
                else:
                    events.event(
                        "audacity",
                        "pipe.failed",
                        "failed to open Audacity pipe for writing",
                        {"error": str(exc), "to": str(pipe_to)},
                    )
                return False

            try:
                # Create a fresh Audacity project before importing stems.
                # This helps keep each replay in its own project/tab/window.
                new_cmds = ["New:\n"]
                if project_name:
                    # Audacity's mod-script-pipe in some versions does not
                    # recognize a SetProjectName batch command. Do not send
                    # an unrecognized command (it causes a BatchCommand failed
                    # response). Instead, log an event so the UI can surface
                    # that the requested name was not applied automatically.
                    events.event(
                        "audacity",
                        "projectname.unsupported",
                        "requested project name will not be set (unsupported command)",
                        {"requested": project_name},
                    )

                for new_cmd in new_cmds:
                    deadline = time.time() + 5.0
                    new_bytes = new_cmd.encode("utf-8")
                    written = 0
                    while written < len(new_bytes) and time.time() < deadline:
                        try:
                            n = os.write(to_fd, new_bytes[written:])
                            if n > 0:
                                written += n
                        except (BlockingIOError, OSError) as e:
                            if e.errno == errno.EAGAIN or isinstance(e, BlockingIOError):
                                time.sleep(0.1)
                                continue
                            else:
                                raise
                    if written < len(new_bytes):
                        events.event(
                            "audacity",
                            "pipe.blocked",
                            "audacity pipe timeout while creating a new project",
                        )
                        return False

                # Give Audacity a moment to create the new project.
                time.sleep(1.5)

                # Send absolute paths so Audacity can resolve them regardless of
                # Audacity's working directory.
                for path in paths:
                    try:
                        path_arg = str(path.resolve())
                    except Exception:
                        # Fall back to the path string if resolution fails.
                        path_arg = str(path)
                    cmd = f'Import2: Filename="{path_arg}"\n'
                    
                    # Write with a timeout by retrying on EAGAIN
                    deadline = time.time() + 5.0
                    cmd_bytes = cmd.encode("utf-8")
                    written = 0
                    while written < len(cmd_bytes) and time.time() < deadline:
                        try:
                            n = os.write(to_fd, cmd_bytes[written:])
                            if n > 0:
                                written += n
                        except (BlockingIOError, OSError) as e:
                            if e.errno == errno.EAGAIN or isinstance(e, BlockingIOError):
                                # Pipe buffer full, wait a bit and retry
                                time.sleep(0.1)
                                continue
                            else:
                                raise
                    
                    if written < len(cmd_bytes):
                        events.event(
                            "audacity",
                            "pipe.blocked",
                            "audacity pipe timeout (Audacity not consuming)",
                        )
                        return False
                    
                    # Give Audacity a moment to process each command.
                    time.sleep(1.5)

                events.event(
                    "audacity",
                    "pipe.completed",
                    "sent import commands to Audacity",
                    {"files": [str(p.resolve()) if p.exists() else str(p) for p in paths]},
                )

                # Attempt to read any responses Audacity wrote to the "from" pipe so
                # we can surface errors (with a short timeout).
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

    # Check if pipes exist already (Audacity running with mod-script-pipe enabled).
    # Only use the pipe route if pipes are already available.

    if pipe_to.exists() and pipe_from.exists():
        events.event("audacity", "audacity.running", "Audacity is already running; using script pipe")
        events.event("audacity", "pipe.available", "Audacity script pipe became available")
        if _send_via_pipe():
            events.event("audacity", "open.completed", "imported stems into Audacity")
            return
        # Pipe write failed — fall through to LOF.
        events.event("audacity", "pipe.failed", "pipe write failed; falling back to LOF import")
    else:
        events.event("audacity", "pipe.unavailable", "script pipe not available; using LOF import")

    # Pipe route not viable. Create a LOF (List of Files) and open it with
    # Audacity. This is the only reliable way to load multiple files into a
    # single project on Linux.
    try:
        lof_path = _write_lof_file(paths)
        cmd = audacity_open_command([lof_path])
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        events.event(
            "audacity",
            "open.completed",
            "opened stems in Audacity via LOF",
            {"command": " ".join(cmd), "lof": str(lof_path)},
        )
    except Exception as exc:
        events.event(
            "audacity",
            "open.failed",
            "failed to open Audacity",
            {"error": str(exc)},
        )


def _write_lof_file(paths: list[Path]) -> Path:
    """Write an Audacity LOF (List of Files) manifest so all stems open in one project."""
    lof_path = paths[0].parent / "stems.lof"
    lines = []
    for path in paths:
        lines.append(f'file "{path.resolve()}" offset 0')
    lof_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return lof_path


def audacity_open_command(paths: list[Path]) -> list[str]:
    path_args = [str(path) for path in paths]
    if sys.platform == "darwin":
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
