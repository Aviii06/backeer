from __future__ import annotations

import argparse
import subprocess
import sys
import os
from datetime import datetime
from pathlib import Path

from .models import WorkflowConfig
from .workflow import run_workflow, replay_audacity, slugify


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="backeer",
        description="Extract YouTube audio, split it with Demucs, and prepare Audacity stems.",
    )
    parser.add_argument("url", nargs="?", help="YouTube URL to process")
    parser.add_argument("--name", help="Human-friendly run name")
    parser.add_argument("--runs-dir", type=Path, default=Path("runs"))
    parser.add_argument("--model", default="htdemucs_6s")
    parser.add_argument(
        "--audacity-pipe",
        action="store_true",
        help="Attempt to import stems into a running Audacity instance through mod-script-pipe.",
    )
    parser.add_argument(
        "--open-audacity",
        "--audacity-open",
        dest="open_audacity",
        action="store_true",
        help="Open the prepared stems in Audacity after the workflow completes.",
    )
    parser.add_argument(
        "--prefect",
        action="store_true",
        help="Run through the Prefect flow so the run appears in the Prefect dashboard.",
    )
    parser.add_argument(
        "--prefect-api-url",
        help=(
            "Prefect API URL to use with --prefect, for example "
            "http://127.0.0.1:4200/api."
        ),
    )
    parser.add_argument(
        "--detach",
        action="store_true",
        help="Start the workflow in the background and redirect launcher output to a log file.",
    )
    parser.add_argument(
        "--replay",
        type=Path,
        help="Replay Audacity preparation from an existing run directory (skips all processing).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    cli_args = list(argv) if argv is not None else sys.argv[1:]
    args = build_parser().parse_args(cli_args)
    
    # Handle replay mode
    if args.replay:
        if args.url or args.prefect or args.detach:
            build_parser().error("--replay cannot be used with URL, --prefect, or --detach")
        try:
            replay_audacity(
                args.replay,
                audacity_pipe=args.audacity_pipe,
                open_audacity=args.open_audacity,
            )
            print(f"\nAudacity replay completed: {args.replay}")
            print(f"Audacity import folder: {args.replay / 'audacity'}")
            return 0
        except Exception as exc:
            raise SystemExit(str(exc)) from exc
    
    if not args.url:
        build_parser().error("URL is required (unless using --replay)")
    if args.prefect_api_url and not args.prefect:
        build_parser().error("--prefect-api-url can only be used with --prefect")
    if args.detach:
        return start_detached(cli_args, args)

    if args.prefect:
        if args.prefect_api_url:
            os.environ["PREFECT_API_URL"] = args.prefect_api_url

        from .prefect_flow import youtube_to_audacity_stems

        try:
            run_dir = youtube_to_audacity_stems(
                args.url,
                name=args.name,
                runs_dir=str(args.runs_dir),
                model=args.model,
                audacity_pipe=args.audacity_pipe,
                open_audacity=args.open_audacity,
            )
        except RuntimeError as exc:
            raise SystemExit(str(exc)) from exc

        print(f"\nPrefect run completed: {run_dir}")
        print(f"Audacity import folder: {Path(run_dir) / 'audacity'}")
        return 0

    config = WorkflowConfig(
        url=args.url,
        name=args.name,
        runs_dir=args.runs_dir,
        model=args.model,
        audacity_pipe=args.audacity_pipe,
        open_audacity=args.open_audacity,
    )
    state = run_workflow(config)
    print(f"\nRun completed: {state.run_dir}")
    print(f"Audacity import folder: {state.run_dir / 'audacity'}")
    return 0


def start_detached(cli_args: list[str], args: argparse.Namespace) -> int:
    child_args = [arg for arg in cli_args if arg != "--detach"]
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    slug = slugify(args.name or "youtube-audio")
    log_dir = args.runs_dir / "daemon"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{stamp}_{slug}.log"
    command = [sys.executable, "-m", "backeer", *child_args]

    with log_path.open("w", encoding="utf-8") as log:
        log.write(f"Starting detached Backeer process: {' '.join(command)}\n")
        log.flush()
        process = subprocess.Popen(
            command,
            stdout=log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )

    print(f"Started Backeer in background with PID {process.pid}")
    print(f"Launcher log: {log_path}")
    if args.prefect:
        print("Prefect run logs will appear in the Prefect dashboard once the run starts.")
    return 0
