# Backeer

Backeer is a local, observable workflow for turning a YouTube music video into Audacity-ready stems.

The default Demucs model is `htdemucs_6s`, which produces:

- `bass.wav`
- `drums.wav`
- `guitar.wav`
- `other.wav`
- `piano.wav`
- `vocals.wav`

## Requirements

Install these command-line tools in your environment:

- `yt-dlp`
- `ffmpeg` and `ffprobe`
- Demucs, runnable as `python -m demucs`

Prefect is optional. The CLI works without it and still writes full run logs.

## Run

Install the package in editable mode from this folder:

```bash
python -m pip install -e .
```

```bash
backeer "https://www.youtube.com/watch?v=..."
```

Useful options:

```bash
backeer URL --name "song-name"
backeer URL --runs-dir ./runs
backeer URL --model htdemucs_6s
backeer URL --audacity-pipe
backeer URL --open-audacity
```

To run the binary through Prefect so the run appears in the dashboard:

```bash
backeer URL --prefect --prefect-api-url http://127.0.0.1:4200/api
```

To start that run in the background and keep the terminal clean:

```bash
backeer URL --prefect --prefect-api-url http://127.0.0.1:4200/api --detach
```

Detached launcher output is written under `runs/daemon/`. Workflow details are still written
to each timestamped run folder, and Prefect run logs appear in the dashboard.

Add `--open-audacity` to open the prepared stems in Audacity when the background run finishes.

## Prefect

Install the optional orchestration dependency:

```bash
python -m pip install -e '.[orchestration]'
```

Start a local Prefect server when you want the UI:

```bash
prefect server start
```

On macOS, you can keep the local Prefect server running with a user LaunchAgent:

```bash
scripts/install-prefect-launchagent.sh
```

Check it:

```bash
launchctl print gui/$(id -u)/com.backeer.prefect-server
tail -f runs/prefect-server/prefect-server.out.log
tail -f runs/prefect-server/prefect-server.err.log
```

Stop and remove it:

```bash
scripts/uninstall-prefect-launchagent.sh
```

Then run the flow from Python:

```bash
python -c "from backeer.prefect_flow import youtube_to_audacity_stems; youtube_to_audacity_stems('URL', name='song-name')"
```

## Run Folder

Each run creates a timestamped folder:

```text
runs/
  2026-05-22_song-name_ab12cd/
    job.json
    events.jsonl
    commands.jsonl
    logs/
    source/
    normalized/
    stems/
    audacity/
    debug/
```

The run folder is the main debugging artifact. Even if a stage fails, logs and partial outputs are preserved.

## Audacity

The workflow always creates an Audacity import folder containing symlinks or copies of the stems plus an `import_order.txt` manifest.

The optional `--audacity-pipe` mode attempts to import stems into a running Audacity instance through `mod-script-pipe`. You must enable that module inside Audacity first.
