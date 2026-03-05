```
██████╗ ██████╗ ███████╗ █████╗ ████████╗██╗  ██╗███████╗
██╔══██╗██╔══██╗██╔════╝██╔══██╗╚══██╔══╝██║  ██║██╔════╝
██████╔╝██████╔╝█████╗  ███████║   ██║   ███████║█████╗
██╔══██╗██╔══██╗██╔══╝  ██╔══██║   ██║   ██╔══██║██╔══╝
██████╔╝██║  ██║███████╗██║  ██║   ██║   ██║  ██║███████╗
╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝╚══════╝
```

<p align="center">
  <strong>Meditation for Vibe Coders</strong>
</p>

<p align="center">
  <em>Breathe while Claude builds. Gong when it's time to code again.</em>
</p>

<p align="center">
  <a href="#techniques">Techniques</a> &middot;
  <a href="#claude-code-hooks">Hooks</a> &middot;
  <a href="#usage">Usage</a> &middot;
  <a href="https://exhuman777.github.io/breathe">Website</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/runtime-Python_3-amber" alt="Python" />
  <img src="https://img.shields.io/badge/deps-zero-black" alt="Zero Dependencies" />
  <img src="https://img.shields.io/badge/vibes-immaculate-orange" alt="Vibes" />
</p>

---

## What

A CLI meditation app that detects when Claude Code is working and lets you breathe in the meantime.

- 3D wireframe geometry that breathes with you
- 7 breathing techniques (box, 4-7-8, Wim Hof, coherent, calm, energy, focus)
- Auto-ends when Claude stops working, needs your input, or timer runs out
- Gong sound on session end
- Warm amber aesthetic. Floating particles. Zero dependencies.

## Install

```bash
# One-liner
curl -fsSL https://raw.githubusercontent.com/exhuman777/breathe/main/breathe.py -o ~/.local/bin/breathe && chmod +x ~/.local/bin/breathe
```

Or clone:
```bash
git clone https://github.com/exhuman777/breathe.git
cd breathe
python3 breathe.py
```

## Usage

```bash
# Interactive technique menu
python3 breathe.py

# Auto-end when Claude finishes
python3 breathe.py --claude

# 10 min Wim Hof session
python3 breathe.py --timer 10 --technique wim

# Silent mode (no sound)
python3 breathe.py --silent
```

### Controls

| Key | Action |
|-----|--------|
| `t` | Cycle breathing technique |
| `s` | Toggle sound |
| `space` | Pause / resume |
| `r` | Reset timer + breath count |
| `q` / `ESC` | Quit |

## Techniques

| Technique | Pattern | Shape | Purpose |
|-----------|---------|-------|---------|
| **Focus** | 4-4-6-2 | Cube | Pre-code clarity |
| **Box** | 4-4-4-4 | Cube | Navy SEAL stress control |
| **4-7-8** | 4-7-8-1 | Octahedron | Deep relaxation |
| **Coherent** | 5.5-5.5 | Cube | HRV optimal (5.5 bpm) |
| **Wim Hof** | 30x fast + 60s hold | Tetrahedron | Power breathing |
| **Calm** | 4-8-1 | Octahedron | Extended exhale |
| **Energy** | 20x fast + 15s hold | Tetrahedron | Kapalabhati activation |

Each technique maps to a unique 3D wireframe shape that rotates and scales with your breath.

## Claude Code Hooks

Auto-launch breathe when Claude starts working. Auto-end when Claude finishes or needs you.

```bash
# Preview hook config
python3 breathe.py --install-hooks

# Install (writes to ~/.claude/settings.json)
python3 breathe.py --install-hooks --confirm
```

This adds three hooks:
- **PreToolUse** (Bash/Edit/Write) — launches breathe in a new Terminal window
- **Stop** — signals breathe to end (Claude finished)
- **Notification** (permission_prompt) — signals breathe to end (Claude needs input)

### How it works

```
Claude starts building
        ↓
   Hook fires (PreToolUse)
        ↓
   breathe launches in new Terminal
        ↓
   You meditate while Claude works
        ↓
   Claude finishes / needs input
        ↓
   Hook fires (Stop / Notification)
        ↓
   Gong plays. Session complete.
        ↓
   Back to coding.
```

## Requirements

- Python 3.6+
- macOS (for Terminal.app hooks + system sounds)
- A terminal that supports Unicode and 256 colors

## Sound

- **Gong** (Glass.aiff x3) plays on session end
- **Tick** (Tink.aiff) plays on breath phase transitions
- Toggle with `s` key or `--silent` flag

---

<p align="center">
  <sub>Built by <a href="https://github.com/exhuman777">exhuman</a>. Breathe between the builds.</sub>
</p>
