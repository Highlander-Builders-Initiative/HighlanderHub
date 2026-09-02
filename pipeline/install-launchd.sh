#!/bin/bash
# Writes a launchd plist for this checkout and loads it. Paths come from this
# script's location so the same file works on any machine.
set -euo pipefail

PIPELINE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LABEL="com.highlanderhub.pipeline"
DEST="${HOME}/Library/LaunchAgents/${LABEL}.plist"

xml_escape() {
  printf '%s' "$1" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'
}

ESCAPED_DIR="$(xml_escape "$PIPELINE_DIR")"

mkdir -p "${HOME}/Library/LaunchAgents"
launchctl unload "$DEST" 2>/dev/null || true

cat > "$DEST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${ESCAPED_DIR}/run_daily.sh</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${ESCAPED_DIR}</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>7</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>RunAtLoad</key>
    <false/>
    <key>StandardOutPath</key>
    <string>${ESCAPED_DIR}/launchd.out.log</string>
    <key>StandardErrorPath</key>
    <string>${ESCAPED_DIR}/launchd.err.log</string>
</dict>
</plist>
EOF

launchctl load "$DEST"
echo "Loaded ${LABEL} (07:00 local). launchctl start ${LABEL} to run now."
