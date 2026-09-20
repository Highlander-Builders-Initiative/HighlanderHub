#!/bin/bash
# Unattended daily wrapper around run.py, installed by ./install-launchd.sh.
#
# Optional local wrapper. GitHub Actions is the supported eight-hour scheduler.
# Do not schedule this wrapper alongside Actions against the same database.
set -uo pipefail

PIPELINE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="$PIPELINE_DIR/pipeline.log"

# Keep the log from growing without bound (rotate past ~5 MB, keep one backup).
if [ -f "$LOG" ] && [ "$(wc -c < "$LOG")" -gt 5242880 ]; then
  mv -f "$LOG" "$LOG.1"
fi

echo "=== $(date '+%Y-%m-%d %H:%M:%S %Z') starting run.py ===" >> "$LOG"
"$PIPELINE_DIR/.venv/bin/python" "$PIPELINE_DIR/run.py" >> "$LOG" 2>&1
status=$?
echo "=== $(date '+%Y-%m-%d %H:%M:%S %Z') run.py exited $status ===" >> "$LOG"

if [ "$status" -ne 0 ]; then
  # run.py isolates per-source failures, so a nonzero exit means at least one
  # source is broken — most often an API or configuration failure.
  osascript -e 'display notification "run.py failed — check pipeline/pipeline.log" with title "HighlanderHub scrape"' >/dev/null 2>&1 || true
fi

exit "$status"
