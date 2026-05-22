#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="com.backeer.prefect-server"
TEMPLATE="$PROJECT_DIR/launchd/$LABEL.plist.template"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST="$LAUNCH_AGENTS_DIR/$LABEL.plist"
LOG_DIR="$PROJECT_DIR/runs/prefect-server"
PREFECT_HOME="${PREFECT_HOME:-$HOME/.prefect}"
PREFECT_BIN="${PREFECT_BIN:-$(command -v prefect)}"

if [[ -z "$PREFECT_BIN" ]]; then
  echo "prefect was not found on PATH. Install Prefect or set PREFECT_BIN=/path/to/prefect." >&2
  exit 1
fi

mkdir -p "$LAUNCH_AGENTS_DIR" "$LOG_DIR" "$PREFECT_HOME"

sed \
  -e "s#__PREFECT_BIN__#$PREFECT_BIN#g" \
  -e "s#__PROJECT_DIR__#$PROJECT_DIR#g" \
  -e "s#__PREFECT_HOME__#$PREFECT_HOME#g" \
  -e "s#__LOG_DIR__#$LOG_DIR#g" \
  "$TEMPLATE" > "$PLIST"

launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl enable "gui/$(id -u)/$LABEL"
launchctl kickstart -k "gui/$(id -u)/$LABEL"

echo "Installed and started $LABEL"
echo "Prefect UI: http://127.0.0.1:4200"
echo "Logs: $LOG_DIR"
