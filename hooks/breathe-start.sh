#!/bin/bash
# Always signal that Claude is working
touch /tmp/breathe-start-signal
# Launch app if not already running
LOCK="/tmp/breathe.lock"
mkdir "$LOCK" 2>/dev/null || exit 0
osascript <<'AS' &
tell application "Terminal"
    activate
    do script "python3 /Users/rufflesrufus/projects/breathe/breathe.py --hook; rm -rf /tmp/breathe.lock; exit"
end tell
AS
exit 0
