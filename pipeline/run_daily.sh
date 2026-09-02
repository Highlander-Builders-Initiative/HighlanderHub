#!/bin/bash
# Unattended daily wrapper around run.py, installed by ./install-launchd.sh.
#
# Runs locally rather than in GitHub Actions on purpose: Instagram sessions
# survive here because (a) the run happens from a residential IP, and (b)
# scrape.py persists the rotated `sessionid` back to IG_SESSION_FILE after
# every run. On a CI runner the session file is ephemeral, so each run replays
# the same increasingly stale cookie until Instagram rejects it.
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
  # source is broken — most often an expired Instagram session.
  osascript -e 'display notification "run.py failed — check pipeline/pipeline.log" with title "HighlanderHub scrape"' >/dev/null 2>&1 || true
fi

exit "$status"
