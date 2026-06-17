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

Install the command-line tools via Homebrew (macOS) or your system package manager:

```bash
brew install yt-dlp ffmpeg python@3.13
```

Then install the Python packages in your environment:

```bash
pip install demucs torchcodec
```

- `yt-dlp` — downloads audio from YouTube
- `ffmpeg` / `ffprobe` — converts and probes audio
- `demucs` — AI stem separation, runnable as `python -m demucs`
- `torchcodec` — required by newer `torchaudio` versions for WAV export

Prefect is optional. The CLI works without it and still writes full run logs.

## Config

Create a `backeer.toml` in your project root (or any ancestor directory) to set defaults:

```toml
[backeer]
model = "htdemucs_6s"
runs-dir = "~/backeer-runs"
with-audacity = true
timezone = "Asia/Kolkata"
```

CLI flags always override config values. Available models: `htdemucs_6s` (6 stems), `htdemucs` (4 stems), `htdemucs_ft` (4 stems, fine-tuned), `mdx_extra` (4 stems).

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
backeer URL --with-audacity
backeer --replay /path/to/run_dir --with-audacity
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
When you pass `--with-audacity` the workflow opens stems in Audacity in a single consolidated project:

- If the mod-script-pipe is available and responding, Backeer sends import commands directly into the running Audacity instance.
- If the script pipe is not available, Backeer writes an Audacity LOF (List of Files) manifest and opens it. This loads all stems into one project on all platforms.

Note: For the best experience with the pipe route, enable the scripting pipe inside Audacity. In recent Audacity versions the option is called "mod-script-pipe" or appears under "Scripting/Tools" in Preferences — enable it and restart Audacity.

Replay mode:

You can replay the Audacity import step from an existing run (so you don't need to re-run download/separate/etc):

```bash
backeer --replay runs/run_2026-06-16_19-02-09_xyz_93623fe8 --with-audacity
```

This recreates the `audacity/` import folder (symlinks/copies) and then attempts to import the stems into Audacity using the scripting pipe.

In replay mode, if the original run failed before stems were separated (e.g. due to a missing
dependency), Backeer detects the missing stems and re-runs the separation step automatically.

## Troubleshooting

**`ModuleNotFoundError: No module named 'torchcodec'`**

Install `torchcodec` in your environment:

```bash
pip install torchcodec
```

This is required by newer `torchaudio` versions (2.11+) for WAV export. If you see this error,
re-run the separation step via replay:

```bash
backeer --replay runs/<run_dir> --with-audacity
```

**Audacity opens multiple windows/separate projects**

On Linux, passing multiple `.wav` files to `audacity` on the command line opens each as a
separate project. Backeer works around this by writing a LOF (List of Files) manifest and
opening it — all stems load into a single project.

If you still see multiple windows, ensure `mod-script-pipe` is enabled in Audacity
(Preferences → Modules → mod-script-pipe → Enabled) and restart Audacity.

**Replay says "no stems available"**

The original run likely failed before separation completed. Backeer now detects this
automatically and re-runs the separation step if normalized audio exists. Install any
missing dependencies first, then replay.
