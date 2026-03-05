#!/usr/bin/env python3
"""
  B R E A T H E
  meditation for vibe coders

  Two states:
    CLAUDE WORKING  → breathe / meditate (3D geometry, breath guide)
    CLAUDE IDLE     → idle companion waits for action (tamagotchi mode)

  Auto-detects Claude Code activity. Gong when you need to act.

  Usage:
    python3 breathe.py              # launch (auto-detects Claude)
    python3 breathe.py --technique box
    python3 breathe.py --hook       # launched by Claude Code hook
    python3 breathe.py --install-hooks --confirm
"""

import curses
import math
import os
import subprocess
import time
import sys
import random
import argparse
import json

# ─── 4 Breathing Techniques ───────────────────────────────────────────
TECHNIQUES = {
    "box": {
        "name": "B O X",
        "desc": "stress control",
        "short": "4-4-4-4",
        "phases": [
            ("inhale", 4), ("hold", 4), ("exhale", 4), ("hold", 4),
        ],
    },
    "relax": {
        "name": "R E L A X",
        "desc": "4-7-8 relaxation",
        "short": "4-7-8",
        "phases": [
            ("inhale", 4), ("hold", 7), ("exhale", 8),
        ],
    },
    "focus": {
        "name": "F O C U S",
        "desc": "clarity breath",
        "short": "4-4-6-2",
        "phases": [
            ("inhale", 4), ("hold", 4), ("exhale", 6), ("rest", 2),
        ],
    },
    "energy": {
        "name": "E N E R G Y",
        "desc": "activation",
        "short": "fast + hold",
        "phases": [
            ("inhale", 1.5), ("exhale", 1.0),
        ],
        "rounds": 20,
        "hold_after": 15,
    },
}

# ─── 3D Shapes ────────────────────────────────────────────────────────
CUBE_V = [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]
CUBE_E = [(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7)]
OCT_V = [(0,-1,0),(1,0,0),(0,0,1),(-1,0,0),(0,0,-1),(0,1,0)]
OCT_E = [(0,1),(0,2),(0,3),(0,4),(5,1),(5,2),(5,3),(5,4),(1,2),(2,3),(3,4),(4,1)]
TET_V = [(1,1,1),(1,-1,-1),(-1,1,-1),(-1,-1,1)]
TET_E = [(0,1),(0,2),(0,3),(1,2),(1,3),(2,3)]

SHAPES = {
    "box": (CUBE_V, CUBE_E),
    "relax": (OCT_V, OCT_E),
    "focus": (CUBE_V, CUBE_E),
    "energy": (TET_V, TET_E),
}

# ─── Tamagotchi frames ────────────────────────────────────────────────
IDLE_FRAMES = [
    [
        r"    ┌─────┐    ",
        r"    │ ◠ ◠ │    ",
        r"    │  ‿  │    ",
        r"    └──┬──┘    ",
        r"   ┌───┴───┐   ",
        r"   │       │   ",
        r"   │  ___  │   ",
        r"   └───────┘   ",
    ],
    [
        r"    ┌─────┐    ",
        r"    │ ─ ─ │    ",
        r"    │  ‿  │    ",
        r"    └──┬──┘    ",
        r"   ┌───┴───┐   ",
        r"   │       │   ",
        r"   │  ___  │   ",
        r"   └───────┘   ",
    ],
    [
        r"    ┌─────┐    ",
        r"    │ ◠ ◠ │    ",
        r"    │  ○  │    ",
        r"    └──┬──┘    ",
        r"   ┌───┴───┐   ",
        r"   │  ?    │   ",
        r"   │  ___  │   ",
        r"   └───────┘   ",
    ],
]

MEDITATING_FRAMES = [
    [
        r"    ┌─────┐    ",
        r"    │ ◡ ◡ │    ",
        r"    │  ‿  │    ",
        r"    └──┬──┘    ",
        r"  ╭───┴───╮   ",
        r"  │  ∙ ∙  │   ",
        r"  │  ╰─╯  │   ",
        r"  ╰───────╯   ",
    ],
    [
        r"    ┌─────┐    ",
        r"    │ ◡ ◡ │    ",
        r"    │  ○  │    ",
        r"    └──┬──┘    ",
        r"  ╭───┴───╮   ",
        r"  │ ∙   ∙ │   ",
        r"  │  ╰─╯  │   ",
        r"  ╰───────╯   ",
    ],
]

ALERT_FRAME = [
    r"    ┌─────┐    ",
    r"    │ ◉ ◉ │    ",
    r"    │  !  │    ",
    r"    └──┬──┘    ",
    r"   ┌───┴───┐   ",
    r"   │  >>>  │   ",
    r"   │  ___  │   ",
    r"   └───────┘   ",
]

HOOK_SIGNAL_FILE = "/tmp/breathe-end-signal"
CLAUDE_CHECK_INTERVAL = 2.0
NUM_PARTICLES = 14


class Particle:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.respawn(True)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.life -= 0.003
        if self.life <= 0 or self.y < 0 or self.x < 0 or self.x >= self.w:
            self.respawn()

    def respawn(self, init=False):
        self.x = random.randint(0, max(1, self.w - 1))
        self.y = random.randint(0, max(1, self.h - 1)) if init else self.h - 1
        self.vx = (random.random() - 0.5) / 5.0
        self.vy = -random.random() / 8.0 - 0.02
        self.life = random.random() if init else 1.0
        self.char = random.choice(['·', '∘', '·', '·'])


def play_gong():
    try:
        for s in ["/System/Library/Sounds/Glass.aiff", "/System/Library/Sounds/Ping.aiff"]:
            if os.path.exists(s):
                subprocess.Popen(
                    f'afplay "{s}" && sleep 0.5 && afplay "{s}" && sleep 0.8 && afplay "{s}"',
                    shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
        sys.stdout.write('\a'); sys.stdout.flush()
    except Exception:
        sys.stdout.write('\a'); sys.stdout.flush()


def play_tick():
    try:
        subprocess.Popen(['afplay', '/System/Library/Sounds/Tink.aiff'],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def play_alert():
    try:
        for s in ["/System/Library/Sounds/Funk.aiff", "/System/Library/Sounds/Glass.aiff"]:
            if os.path.exists(s):
                subprocess.Popen(['afplay', s],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
    except Exception:
        pass


def detect_claude_status():
    try:
        result = subprocess.run(['pgrep', '-f', 'claude'],
                               capture_output=True, text=True, timeout=2)
        if result.returncode != 0:
            return "absent"
        pids = [p for p in result.stdout.strip().split('\n') if p]
        max_cpu = 0.0
        for pid in pids:
            try:
                ps = subprocess.run(['ps', '-p', pid, '-o', '%cpu='],
                                   capture_output=True, text=True, timeout=2)
                cpu = float(ps.stdout.strip())
                max_cpu = max(max_cpu, cpu)
            except (ValueError, subprocess.TimeoutExpired):
                continue
        if max_cpu > 10.0:
            return "working"
        elif max_cpu > 2.0:
            return "idle"
        else:
            return "waiting"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "absent"


def check_hook_signal():
    if os.path.exists(HOOK_SIGNAL_FILE):
        try: os.remove(HOOK_SIGNAL_FILE)
        except OSError: pass
        return True
    return False


def rotate_point(x, y, z, ax, ay):
    ca, sa = math.cos(ax), math.sin(ax)
    y2, z2 = y*ca - z*sa, y*sa + z*ca
    cb, sb = math.cos(ay), math.sin(ay)
    return x*cb + z2*sb, y2, -x*sb + z2*cb


def project(x, y, z, cx, cy, scale):
    f = 4.0 / (4.0 + z)
    return int(cx + x*scale*f*2), int(cy + y*scale*f), f


def bresenham(x0, y0, x1, y1):
    pts = []
    dx, dy = abs(x1-x0), abs(y1-y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    for _ in range(500):
        pts.append((x0, y0))
        if x0 == x1 and y0 == y1: break
        e2 = 2 * err
        if e2 > -dy: err -= dy; x0 += sx
        if e2 < dx: err += dx; y0 += sy
    return pts


class BreathEngine:
    def __init__(self, key):
        self.key = key
        self.tech = TECHNIQUES[key]
        self.phases = self.tech["phases"]
        self.cycle_len = sum(d for _, d in self.phases)
        self.rounds = self.tech.get("rounds")
        self.hold_after = self.tech.get("hold_after")
        self.round_count = 0

    def get_phase(self, elapsed):
        if self.rounds and self.hold_after:
            rt = self.rounds * self.cycle_len
            total = rt + self.hold_after
            cp = elapsed % total
            if cp < rt:
                self.round_count = int(cp / self.cycle_len) + 1
                return self._at(cp % self.cycle_len)
            return ("hold", (cp - rt) / self.hold_after, self.hold_after)
        return self._at(elapsed % self.cycle_len)

    def _at(self, pos):
        for name, dur in self.phases:
            if pos < dur:
                return (name, pos / dur, dur)
            pos -= dur
        n, d = self.phases[-1]
        return (n, 1.0, d)


def fmt_time(s):
    return f"{int(s)//60:02d}:{int(s)%60:02d}"


def safe_add(scr, y, x, text, attr=0):
    h, w = scr.getmaxyx()
    if 0 <= y < h and 0 <= x < w:
        try: scr.addnstr(y, x, text, w - x - 1, attr)
        except curses.error: pass


def center(scr, y, text, attr=0):
    _, w = scr.getmaxyx()
    safe_add(scr, y, max(0, (w - len(text)) // 2), text, attr)


def draw_tamagotchi(scr, cy, cx, frames, frame_idx, attr):
    frame = frames[frame_idx % len(frames)]
    start_y = cy - len(frame) // 2
    for i, line in enumerate(frame):
        safe_add(scr, start_y + i, cx - len(line) // 2, line, attr)


def main(stdscr):
    global args
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(50)

    curses.start_color()
    curses.use_default_colors()
    if curses.can_change_color():
        curses.init_color(10, 900, 600, 200)
        curses.init_color(11, 600, 400, 150)
        curses.init_color(12, 400, 250, 100)
        curses.init_color(13, 200, 130, 50)
        curses.init_color(14, 1000, 700, 300)
        curses.init_color(15, 300, 900, 400)
        curses.init_color(16, 900, 300, 300)
        curses.init_pair(1, 10, -1)
        curses.init_pair(2, 11, -1)
        curses.init_pair(3, 12, -1)
        curses.init_pair(4, 13, -1)
        curses.init_pair(5, 14, -1)
        curses.init_pair(6, 15, -1)
        curses.init_pair(7, 16, -1)
    else:
        curses.init_pair(1, curses.COLOR_YELLOW, -1)
        curses.init_pair(2, curses.COLOR_YELLOW, -1)
        curses.init_pair(3, curses.COLOR_WHITE, -1)
        curses.init_pair(4, curses.COLOR_WHITE, -1)
        curses.init_pair(5, curses.COLOR_YELLOW, -1)
        curses.init_pair(6, curses.COLOR_GREEN, -1)
        curses.init_pair(7, curses.COLOR_RED, -1)

    C_AMBER = curses.color_pair(1)
    C_DIM = curses.color_pair(2)
    C_VDIM = curses.color_pair(3)
    C_GHOST = curses.color_pair(4)
    C_BRIGHT = curses.color_pair(5)
    C_GREEN = curses.color_pair(6)
    C_RED = curses.color_pair(7)

    h, w = stdscr.getmaxyx()
    tech_keys = list(TECHNIQUES.keys())
    tech_idx = tech_keys.index(args.technique) if args.technique else 0
    engine = BreathEngine(tech_keys[tech_idx])
    verts, edges = SHAPES[tech_keys[tech_idx]]

    start_time = time.time()
    last_claude_check = 0
    claude_status = "absent"
    angle_x = angle_y = 0.0
    session_breaths = 0
    last_phase = ""
    last_phase_name = None
    sound_on = not args.silent
    particles = [Particle(w, h) for _ in range(NUM_PARTICLES)]
    idle_frame_t = 0
    alert_played = False
    was_working = False
    meditation_elapsed = 0.0
    meditation_start = None
    mode = "idle"

    while True:
        try: key = stdscr.getch()
        except: key = -1

        if key == ord('q') or key == 27:
            break
        elif key == ord('t') or key == ord('T'):
            tech_idx = (tech_idx + 1) % len(tech_keys)
            engine = BreathEngine(tech_keys[tech_idx])
            verts, edges = SHAPES[tech_keys[tech_idx]]
        elif key == ord('s') or key == ord('S'):
            sound_on = not sound_on

        now = time.time()

        if check_hook_signal():
            if sound_on: play_gong()
            break

        if now - last_claude_check > CLAUDE_CHECK_INTERVAL:
            claude_status = detect_claude_status()
            last_claude_check = now

            if claude_status == "working":
                was_working = True
                if mode != "breathe":
                    mode = "breathe"
                    meditation_start = now
                    session_breaths = 0
                    start_time = now
                    alert_played = False
            elif was_working and claude_status in ("waiting", "absent", "idle"):
                if mode == "breathe":
                    meditation_elapsed += (now - (meditation_start or now))
                mode = "idle"
                if not alert_played:
                    alert_played = True
                    if sound_on: play_alert()

        h, w = stdscr.getmaxyx()
        if h < 12 or w < 44:
            stdscr.erase()
            safe_add(stdscr, 0, 0, "need 44x12 min", C_RED)
            stdscr.refresh()
            time.sleep(0.1)
            continue

        for p in particles:
            p.w, p.h = w, h
            p.update()

        stdscr.erase()

        for p in particles:
            px, py = int(p.x), int(p.y)
            if 0 <= py < h-1 and 0 <= px < w-1:
                pr = C_GHOST if p.life < 0.3 else (C_VDIM if p.life < 0.6 else C_DIM)
                safe_add(stdscr, py, px, p.char, pr)

        center(stdscr, 0, "B R E A T H E", C_BRIGHT | curses.A_BOLD)

        if mode == "breathe":
            elapsed = now - start_time
            phase_name, progress, phase_dur = engine.get_phase(elapsed)

            if phase_name == "inhale" and last_phase != "inhale":
                session_breaths += 1
            last_phase = phase_name

            if sound_on and phase_name != last_phase_name and last_phase_name is not None:
                play_tick()
            last_phase_name = phase_name

            angle_x += 0.008
            angle_y += 0.012

            cx, cy_shape = w // 2, h // 2 - 3
            if phase_name == "inhale": scale = 3.0 + progress * 2.5
            elif phase_name == "hold": scale = 5.5 + math.sin(now * 2) * 0.2
            elif phase_name == "exhale": scale = 5.5 - progress * 2.5
            else: scale = 3.0

            proj = []
            for vx, vy, vz in verts:
                rx, ry, rz = rotate_point(vx, vy, vz, angle_x, angle_y)
                sx, sy, f = project(rx, ry, rz, cx, cy_shape, scale)
                proj.append((sx, sy, f))

            for e0, e1 in edges:
                x0, y0, f0 = proj[e0]
                x1, y1, f1 = proj[e1]
                pts = bresenham(x0, y0, x1, y1)
                af = (f0 + f1) / 2
                for px, py in pts:
                    if 0 <= py < h-1 and 0 <= px < w-1:
                        if af > 0.85: ch, cp = '█', C_AMBER
                        elif af > 0.7: ch, cp = '▓', C_AMBER
                        elif af > 0.55: ch, cp = '░', C_DIM
                        else: ch, cp = '·', C_VDIM
                        safe_add(stdscr, py, px, ch, cp)

            for sx, sy, f in proj:
                if 0 <= sy < h-1 and 0 <= sx < w-1:
                    safe_add(stdscr, sy, sx, '◆', C_BRIGHT | curses.A_BOLD)

            center(stdscr, 1, engine.tech["name"], C_DIM)

            phase_labels = {
                "inhale": "▲  I N H A L E  ▲",
                "hold":   "◆  H O L D  ◆",
                "exhale": "▼  E X H A L E  ▼",
                "rest":   "·  R E S T  ·",
            }
            label = phase_labels.get(phase_name, phase_name)
            gy = h // 2 + 4

            bar_w = min(32, w - 8)
            filled = int(progress * bar_w)
            bar = '━' * filled + '╸' + '─' * max(0, bar_w - filled - 1)

            center(stdscr, gy, label, C_BRIGHT | curses.A_BOLD)
            center(stdscr, gy + 1, bar, C_AMBER)

            if engine.rounds:
                center(stdscr, gy + 2, f"round {engine.round_count}/{engine.rounds}", C_DIM)

            center(stdscr, gy + 3, f"◇ {fmt_time(elapsed)}  ·  {session_breaths} cycles", C_AMBER)
            center(stdscr, h - 4, "● C L A U D E   I S   B U I L D I N G", C_GREEN | curses.A_BOLD)

        else:
            idle_frame_t += 1
            needs_action = claude_status in ("waiting", "absent") and was_working
            tama_cx = w // 2
            tama_cy = h // 2 - 2

            if needs_action:
                blink = (idle_frame_t // 10) % 2
                draw_tamagotchi(stdscr, tama_cy, tama_cx, [ALERT_FRAME], 0,
                               C_RED | curses.A_BOLD if blink else C_BRIGHT | curses.A_BOLD)
                center(stdscr, 1, "◈ ◈ ◈  A C T I O N   N E E D E D  ◈ ◈ ◈", C_RED | curses.A_BOLD)
                if claude_status == "waiting":
                    center(stdscr, h // 2 + 4, "Claude needs your input", C_BRIGHT | curses.A_BOLD)
                else:
                    center(stdscr, h // 2 + 4, "Claude finished building", C_BRIGHT | curses.A_BOLD)
                center(stdscr, h // 2 + 5, "switch to Claude Code", C_DIM)
                if meditation_elapsed > 0:
                    center(stdscr, h // 2 + 7,
                           f"session: {fmt_time(meditation_elapsed)}  ·  {session_breaths} cycles", C_AMBER)
            else:
                fidx = (idle_frame_t // 40) % len(IDLE_FRAMES)
                if idle_frame_t % 200 < 10:
                    fidx = 1
                draw_tamagotchi(stdscr, tama_cy, tama_cx, IDLE_FRAMES, fidx, C_AMBER)
                center(stdscr, 1, "waiting for claude to start working...", C_DIM)
                msgs = [
                    "start building something and i'll guide your breath",
                    "i wake up when claude wakes up",
                    "your meditation companion is here",
                    "energy follows attention",
                ]
                center(stdscr, h // 2 + 4, msgs[(idle_frame_t // 120) % len(msgs)], C_VDIM)
                status_map = {
                    "absent": ("○ no claude process", C_GHOST),
                    "idle": ("◌ claude is idle", C_DIM),
                    "waiting": ("◇ claude is waiting", C_DIM),
                }
                st, sc = status_map.get(claude_status, ("?", C_GHOST))
                center(stdscr, h - 4, st, sc)

        # Controls — always visible
        tech = TECHNIQUES[tech_keys[tech_idx]]
        snd = "on" if sound_on else "off"
        center(stdscr, h - 2,
               f"[t] {tech['name']} {tech['short']}  [s] sound:{snd}  [q] quit",
               C_AMBER | curses.A_BOLD)

        selector = "  ".join(
            f"{'▸' if i == tech_idx else ' '}{k.upper()}"
            for i, k in enumerate(tech_keys)
        )
        center(stdscr, h - 1, selector, C_DIM)

        stdscr.refresh()
        time.sleep(0.05)


def install_hooks():
    hooks_dir = os.path.expanduser("~/.claude/hooks")
    os.makedirs(hooks_dir, exist_ok=True)
    script_path = os.path.abspath(__file__)

    start_script = f"""#!/bin/bash
LOCK="/tmp/breathe.lock"
mkdir "$LOCK" 2>/dev/null || exit 0
osascript <<'AS' &
tell application "Terminal"
    activate
    do script "python3 {script_path} --hook; rm -rf /tmp/breathe.lock; exit"
end tell
AS
exit 0
"""
    stop_script = """#!/bin/bash
touch /tmp/breathe-end-signal
exit 0
"""
    start_path = os.path.join(hooks_dir, "breathe-start.sh")
    stop_path = os.path.join(hooks_dir, "breathe-stop.sh")
    with open(start_path, 'w') as f: f.write(start_script)
    os.chmod(start_path, 0o755)
    with open(stop_path, 'w') as f: f.write(stop_script)
    os.chmod(stop_path, 0o755)

    settings_path = os.path.expanduser("~/.claude/settings.json")
    settings = {}
    if os.path.exists(settings_path):
        with open(settings_path) as f: settings = json.load(f)
    hooks = settings.get("hooks", {})

    def has_breathe(lst):
        return any("breathe" in h.get("command", "") for e in lst for h in e.get("hooks", []))

    for event in ["PreToolUse", "Stop", "Notification"]:
        hooks.setdefault(event, [])

    if not has_breathe(hooks["PreToolUse"]):
        hooks["PreToolUse"].append({
            "matcher": "Bash|Edit|Write",
            "hooks": [{"type": "command", "command": f"bash {start_path}", "async": True}]
        })
    if not has_breathe(hooks["Stop"]):
        hooks["Stop"].append({
            "matcher": "",
            "hooks": [{"type": "command", "command": f"bash {stop_path}"}]
        })
    if not has_breathe(hooks["Notification"]):
        hooks["Notification"].append({
            "matcher": "permission_prompt",
            "hooks": [{"type": "command", "command": f"bash {stop_path}"}]
        })

    settings["hooks"] = hooks
    print(f"\n  Hooks: {hooks_dir}/")
    print(json.dumps({"hooks": hooks}, indent=2))
    if "--confirm" in sys.argv:
        with open(settings_path, 'w') as f: json.dump(settings, f, indent=2)
        print(f"\n  Written to {settings_path}")
    else:
        print(f"\n  Add --confirm to apply")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="B R E A T H E")
    parser.add_argument("--hook", action="store_true")
    parser.add_argument("--technique", choices=list(TECHNIQUES.keys()))
    parser.add_argument("--silent", action="store_true")
    parser.add_argument("--install-hooks", action="store_true")
    args = parser.parse_args()
    if args.install_hooks:
        install_hooks()
        sys.exit(0)
    try:
        curses.wrapper(main)
        print("\n  namaste.\n")
    except KeyboardInterrupt:
        print("\n  namaste.\n")
