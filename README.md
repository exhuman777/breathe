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
  <a href="#how-it-works">How it Works</a> &middot;
  <a href="#techniques">Techniques</a> &middot;
  <a href="#claude-code-hooks">Hooks</a> &middot;
  <a href="https://exhuman777.github.io/breathe">Website</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/runtime-Python_3-amber" alt="Python" />
  <img src="https://img.shields.io/badge/deps-zero-black" alt="Zero Dependencies" />
  <img src="https://img.shields.io/badge/vibes-immaculate-orange" alt="Vibes" />
</p>

---

## What

A CLI meditation companion for developers using Claude Code.

**Two modes:**

- **Claude building** → 3D wireframe geometry breathes with you. Guided breathing. Timer.
- **Claude idle / needs you** → Tamagotchi companion waits. Alerts when action needed.

Meditation starts automatically when Claude starts working. Ends with a gong when Claude finishes or needs your input. Zero deps. Pure Python.

## Install

```bash
# One-liner
curl -fsSL https://raw.githubusercontent.com/exhuman777/breathe/main/breathe.py -o ~/.local/bin/breathe && chmod +x ~/.local/bin/breathe
```

```bash
# Clone
git clone https://github.com/exhuman777/breathe.git
cd breathe && python3 breathe.py
```

## How it Works

```
You give Claude a task
        ↓
Claude starts building (high CPU)
        ↓
   BREATHE activates → 3D geometry + guided breathing
        ↓
Claude finishes / needs input / permission
        ↓
   GONG → tamagotchi alert → "ACTION NEEDED"
        ↓
You switch back to code
```

When Claude is idle, a small ASCII companion waits for you. It blinks, looks around, shows rotating messages. Tech-romantic digital pet energy.

## Techniques

| Key | Technique | Pattern | Purpose |
|-----|-----------|---------|---------|
| **box** | Box | 4-4-4-4 | Stress control |
| **relax** | 4-7-8 | 4-7-8 | Deep relaxation |
| **focus** | Focus | 4-4-6-2 | Clarity |
| **energy** | Energy | 20x fast + 15s hold | Activation |

Press `t` to cycle techniques during a session. Each maps to a unique 3D wireframe shape.

## Claude Code Hooks

Auto-launch breathe when Claude works. Auto-end when done.

```bash
python3 breathe.py --install-hooks --confirm
```

Three hooks:
- **PreToolUse** (Bash/Edit/Write) → launches in new Terminal (atomic lock, only one window ever)
- **Stop** → signals end (Claude finished)
- **Notification** (permission_prompt) → signals end (Claude needs input)

## Controls

| Key | Action |
|-----|--------|
| `t` | Cycle breathing technique |
| `s` | Toggle sound on/off |
| `q` / `ESC` | Quit |

## Sound

- **Gong** (Glass.aiff x3) → session end
- **Alert** (Funk.aiff) → action needed
- **Tick** (Tink.aiff) → breath phase transitions
- `--silent` flag or `s` key to mute

## Requirements

- Python 3.6+
- macOS (Terminal.app hooks + system sounds)
- Terminal with Unicode + 256 colors

---

<p align="center">
  <sub>Built by <a href="https://github.com/exhuman777">exhuman</a>. Breathe between the builds.</sub>
</p>
