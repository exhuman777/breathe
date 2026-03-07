# CLAUDE.md — breAIth

## What This Is

CLI meditation companion for vibe coders. Breathe while Claude builds. Gong when it's your turn.

Single Python file (`breathe.py`), zero deps, curses TUI, macOS-native sounds.

## Architecture

```
breathe.py          — entire app (single file)
hooks/              — shell scripts for Claude Code integration
  breathe-start.sh  — touch /tmp/breathe-start-signal
  breathe-stop.sh   — touch /tmp/breathe-end-signal
docs/
  index.html        — landing page (GitHub Pages)
~/.breaith/         — runtime config + journal (NOT in repo)
  config.json       — saved mode + technique preference
  journal.md        — post-meditation entries
```

## App States

```
SETUP  → pick mode (breathing / meditation) + technique
IDLE   → ambient starfield, waiting for Claude activity
ACTIVE → Claude is building, breathing/meditation plays
JOURNAL → gong, optional thought capture, then back to IDLE
```

## Activation Flow

1. Claude Code hooks touch `/tmp/breathe-start-signal` on PreToolUse (Bash/Edit/Write) + UserPromptSubmit
2. SessionStart/SessionEnd hooks manage `/tmp/breathe-session-active` lifecycle file
3. JSONL file monitoring: checks `~/.claude/projects/` transcript mtime (zero subprocesses, pure `os.stat()`)
4. Detection returns "thinking" (JSONL modified <8s), "exists" (session file present), or "absent"
5. App enters ACTIVE state with 3D wireframe + guided breathing
6. End signal (`/tmp/breathe-end-signal`) or 12s idle timeout → gong → journal → IDLE

## Key Code Sections

| Section | What |
|---------|------|
| `TECHNIQUES` dict (L29-38) | Breathing patterns: box, relax, focus, energy |
| `SHAPES` (L42-48) | 3D wireframe vertices + edges per technique |
| `BreathEngine` class (L134-149) | Phase timing + progress calculation |
| `setup_screen()` (L183-248) | Mode selection TUI |
| `journal_screen()` (L251-314) | Post-meditation text input |
| `main()` (L318-651) | Main loop: idle/active states, rendering, signals |
| `install_hooks()` (L654-681) | Writes Claude Code hook config |

## Conventions

- **Single file.** Don't split into modules. Simplicity is the feature.
- **Zero dependencies.** stdlib only (curses, math, os, subprocess, time, json, argparse, random).
- **macOS-first.** System sounds via `afplay`, terminal via curses. Fallback to bell char.
- **Config at `~/.breaith/`.** Never store runtime state in the repo.
- **Short variable names in render code** — `sa()`, `ctr()`, `C`, `h`, `w` — this is intentional for dense render loops.

## Controls

| Key | Action |
|-----|--------|
| `t` | Cycle breathing technique |
| `s` | Toggle sound |
| `←` / `h` | Back to setup menu |
| `Esc` | Back to menu (from active) |
| `q` | Quit |

## CLI Flags

```
python3 breathe.py                            # normal launch
python3 breathe.py --technique box            # start with specific technique
python3 breathe.py --silent                   # no sound
python3 breathe.py --install-hooks --confirm  # install Claude Code hooks
```

## Rules for Changes

1. Keep it one file. No splitting.
2. No external dependencies. Ever.
3. Test curses changes visually — can't unit test TUI rendering.
4. Sound files are macOS system sounds — don't bundle audio.
5. Hook signal files go to `/tmp/` — ephemeral by design.
6. Don't touch `~/.claude/settings.json` without `--install-hooks --confirm`.
7. The `.breaith` config dir is `~/.breaith/`, not in the repo.
