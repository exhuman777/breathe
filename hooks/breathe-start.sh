#!/bin/bash
# breathe: start meditation when Claude starts working
# Uses mkdir as atomic lock — cannot race
LOCK="/tmp/breathe.lock"
SCRIPT="/Users/rufflesrufus/Rufus/scripts/breathe.py"

# Atomic lock: mkdir fails if dir already exists (no race condition)
if ! mkdir "$LOCK" 2>/dev/null; then
    # Lock exists — check if stale (older than 2 hours)
    if [ -d "$LOCK" ]; then
        AGE=$(( $(date +%s) - $(stat -f %m "$LOCK") ))
        if [ "$AGE" -lt 7200 ]; then
            exit 0
        fi
        rm -rf "$LOCK"
        mkdir "$LOCK" 2>/dev/null || exit 0
    else
        exit 0
    fi
fi

# Lock acquired. Launch in new Terminal window.
osascript <<'APPLESCRIPT' &
tell application "Terminal"
    activate
    do script "python3 /Users/rufflesrufus/Rufus/scripts/breathe.py --claude --technique focus; rm -rf /tmp/breathe.lock; exit"
end tell
APPLESCRIPT

exit 0
