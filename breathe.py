#!/usr/bin/env python3
"""
  B R E A T H E
  meditation for vibe coders

  Detects when Claude Code is working.
  Ends when: Claude stops, needs permission, timer runs out.
  Gong sound on session end.

  Usage:
    python3 breathe.py              # standalone, infinite
    python3 breathe.py --claude     # auto-end when Claude stops/needs input
    python3 breathe.py --hook       # launched by Claude Code hook (auto-end)
    python3 breathe.py --timer 10   # 10 minute timer
    python3 breathe.py --technique box  # specific breathing technique

  Aesthetic: Invisible Architecture. dark, monospace, warm amber, geometric.
"""

import curses
import math
import os
import subprocess
import time
import signal
import sys
import random
import argparse
import json

# ─── Breathing Techniques ─────────────────────────────────────────────
TECHNIQUES = {
    "box": {
        "name": "B O X",
        "desc": "Navy SEAL stress control",
        "phases": [
            ("inhale",  4),
            ("hold",    4),
            ("exhale",  4),
            ("hold",    4),
        ],
    },
    "478": {
        "name": "4 - 7 - 8",
        "desc": "Dr. Weil relaxation response",
        "phases": [
            ("inhale",  4),
            ("hold",    7),
            ("exhale",  8),
            ("rest",    1),
        ],
    },
    "coherent": {
        "name": "C O H E R E N T",
        "desc": "5.5 breaths/min HRV optimal",
        "phases": [
            ("inhale",  5.5),
            ("exhale",  5.5),
        ],
    },
    "wim": {
        "name": "W I M   H O F",
        "desc": "Power breathing. 30 fast + hold",
        "phases": [
            ("inhale",  1.5),
            ("exhale",  1.0),
        ],
        "rounds": 30,
        "hold_after": 60,
    },
    "calm": {
        "name": "C A L M",
        "desc": "Simple extended exhale",
        "phases": [
            ("inhale",  4),
            ("exhale",  8),
            ("rest",    1),
        ],
    },
    "energy": {
        "name": "E N E R G Y",
        "desc": "Kapalabhati-inspired activation",
        "phases": [
            ("exhale",  0.5),
            ("inhale",  0.5),
        ],
        "rounds": 20,
        "hold_after": 15,
    },
    "focus": {
        "name": "F O C U S",
        "desc": "Pre-code clarity breath",
        "phases": [
            ("inhale",  4),
            ("hold",    4),
            ("exhale",  6),
            ("rest",    2),
        ],
    },
}

DEFAULT_TECHNIQUE = "focus"

# ─── 3D Wireframe Geometries ──────────────────────────────────────────
CUBE_VERTICES = [
    (-1, -1, -1), ( 1, -1, -1), ( 1,  1, -1), (-1,  1, -1),
    (-1, -1,  1), ( 1, -1,  1), ( 1,  1,  1), (-1,  1,  1),
]
CUBE_EDGES = [
    (0,1),(1,2),(2,3),(3,0),
    (4,5),(5,6),(6,7),(7,4),
    (0,4),(1,5),(2,6),(3,7),
]

# Octahedron
OCT_VERTICES = [
    ( 0, -1,  0), ( 1,  0,  0), ( 0,  0,  1),
    (-1,  0,  0), ( 0,  0, -1), ( 0,  1,  0),
]
OCT_EDGES = [
    (0,1),(0,2),(0,3),(0,4),
    (5,1),(5,2),(5,3),(5,4),
    (1,2),(2,3),(3,4),(4,1),
]

# Tetrahedron
TET_VERTICES = [
    ( 1,  1,  1), ( 1, -1, -1), (-1,  1, -1), (-1, -1,  1),
]
TET_EDGES = [
    (0,1),(0,2),(0,3),(1,2),(1,3),(2,3),
]

SHAPES = {
    "box":      (CUBE_VERTICES, CUBE_EDGES),
    "478":      (OCT_VERTICES, OCT_EDGES),
    "coherent": (CUBE_VERTICES, CUBE_EDGES),
    "wim":      (TET_VERTICES, TET_EDGES),
    "calm":     (OCT_VERTICES, OCT_EDGES),
    "energy":   (TET_VERTICES, TET_EDGES),
    "focus":    (CUBE_VERTICES, CUBE_EDGES),
}

NUM_PARTICLES = 18
CLAUDE_CHECK_INTERVAL = 2.0
GONG_PID_FILE = "/tmp/breathe-gong.pid"
HOOK_SIGNAL_FILE = "/tmp/breathe-end-signal"

# ─── Particle ─────────────────────────────────────────────────────────
class Particle:
    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.respawn(init=True)

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
        self.char = '·' if random.random() > 0.3 else '∘'


# ─── Sound ────────────────────────────────────────────────────────────
def play_gong():
    """Play a gong/bell sound using macOS system sounds."""
    try:
        # Try multiple approaches for a meditation bell sound
        # 1. afplay with system sounds
        sounds = [
            "/System/Library/Sounds/Glass.aiff",
            "/System/Library/Sounds/Ping.aiff",
            "/System/Library/Sounds/Purr.aiff",
        ]
        for s in sounds:
            if os.path.exists(s):
                # Play it 3 times with delay for a gong-like effect
                subprocess.Popen(
                    f'afplay "{s}" && sleep 0.5 && afplay "{s}" && sleep 0.8 && afplay "{s}"',
                    shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                return True
        # 2. Fallback: terminal bell
        sys.stdout.write('\a')
        sys.stdout.flush()
        return True
    except Exception:
        sys.stdout.write('\a')
        sys.stdout.flush()
        return False


def play_tick():
    """Subtle tick for breath transitions."""
    try:
        subprocess.Popen(
            ['afplay', '/System/Library/Sounds/Tink.aiff'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except Exception:
        pass


# ─── Claude Detection ─────────────────────────────────────────────────
def detect_claude_status():
    """
    Returns:
        "working"    - Claude is actively processing (high CPU)
        "waiting"    - Claude needs input/permission (process exists, low CPU)
        "idle"       - Claude process exists but idle
        "absent"     - No Claude process found
    """
    try:
        result = subprocess.run(
            ['pgrep', '-f', 'claude'],
            capture_output=True, text=True, timeout=2
        )
        if result.returncode != 0:
            return "absent"

        pids = [p for p in result.stdout.strip().split('\n') if p]
        max_cpu = 0.0

        for pid in pids:
            try:
                ps = subprocess.run(
                    ['ps', '-p', pid, '-o', '%cpu='],
                    capture_output=True, text=True, timeout=2
                )
                cpu = float(ps.stdout.strip())
                max_cpu = max(max_cpu, cpu)
            except (ValueError, subprocess.TimeoutExpired):
                continue

        if max_cpu > 10.0:
            return "working"
        elif max_cpu > 2.0:
            return "idle"
        else:
            # Low CPU could mean waiting for input
            return "waiting"

    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "absent"


def check_hook_signal():
    """Check if a hook has signaled us to end."""
    if os.path.exists(HOOK_SIGNAL_FILE):
        try:
            os.remove(HOOK_SIGNAL_FILE)
        except OSError:
            pass
        return True
    return False


# ─── 3D Math ──────────────────────────────────────────────────────────
def rotate_point(x, y, z, ax, ay):
    cos_a, sin_a = math.cos(ax), math.sin(ax)
    y2 = y * cos_a - z * sin_a
    z2 = y * sin_a + z * cos_a
    cos_b, sin_b = math.cos(ay), math.sin(ay)
    x2 = x * cos_b + z2 * sin_b
    z3 = -x * sin_b + z2 * cos_b
    return x2, y2, z3


def project(x, y, z, cx, cy, scale):
    dist = 4.0
    factor = dist / (dist + z)
    sx = int(cx + x * scale * factor * 2)
    sy = int(cy + y * scale * factor)
    return sx, sy, factor


def draw_line_chars(x0, y0, x1, y1):
    points = []
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    limit = 500  # safety
    while limit > 0:
        points.append((x0, y0))
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x0 += sx
        if e2 < dx:
            err += dx
            y0 += sy
        limit -= 1
    return points


# ─── Breath Engine ────────────────────────────────────────────────────
class BreathEngine:
    def __init__(self, technique_key):
        self.technique_key = technique_key
        self.tech = TECHNIQUES[technique_key]
        self.phases = self.tech["phases"]
        self.cycle_len = sum(dur for _, dur in self.phases)
        self.rounds = self.tech.get("rounds", None)
        self.hold_after = self.tech.get("hold_after", None)
        self.round_count = 0
        self.in_hold_phase = False
        self.hold_start = None

    def get_phase(self, elapsed):
        """Returns (phase_name, progress_0_to_1, phase_duration)."""
        # Wim Hof / Energy: round-based with retention hold
        if self.rounds and self.hold_after:
            rounds_time = self.rounds * self.cycle_len
            total_round = rounds_time + self.hold_after

            cycle_pos = elapsed % total_round
            if cycle_pos < rounds_time:
                self.in_hold_phase = False
                self.round_count = int(cycle_pos / self.cycle_len) + 1
                inner = cycle_pos % self.cycle_len
                return self._phase_at(inner)
            else:
                self.in_hold_phase = True
                hold_elapsed = cycle_pos - rounds_time
                return ("hold", hold_elapsed / self.hold_after, self.hold_after)

        # Normal cycling
        pos = elapsed % self.cycle_len
        return self._phase_at(pos)

    def _phase_at(self, pos):
        for name, dur in self.phases:
            if pos < dur:
                return (name, pos / dur, dur)
            pos -= dur
        name, dur = self.phases[-1]
        return (name, 1.0, dur)

    def get_round_info(self):
        if self.rounds:
            return f"round {self.round_count}/{self.rounds}"
        return None


# ─── Drawing ──────────────────────────────────────────────────────────
def format_time(seconds):
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m:02d}:{s:02d}"


def safe_addstr(stdscr, y, x, text, attr=0):
    h, w = stdscr.getmaxyx()
    if 0 <= y < h and 0 <= x < w:
        try:
            stdscr.addnstr(y, x, text, w - x - 1, attr)
        except curses.error:
            pass


def draw_centered(stdscr, y, text, attr=0):
    _, w = stdscr.getmaxyx()
    x = max(0, (w - len(text)) // 2)
    safe_addstr(stdscr, y, x, text, attr)


def show_completion_screen(stdscr, session_breaths, elapsed, reason, h, w):
    """Show session complete screen with gong."""
    play_gong()

    stdscr.erase()

    reasons = {
        "timer":      "timer complete",
        "claude_done": "claude finished",
        "claude_input": "claude needs you",
        "hook":       "hook signal received",
        "quit":       "session ended",
    }
    reason_text = reasons.get(reason, reason)

    draw_centered(stdscr, h // 2 - 3,
        "◆  S E S S I O N   C O M P L E T E  ◆",
        curses.color_pair(5) | curses.A_BOLD)

    draw_centered(stdscr, h // 2 - 1, reason_text, curses.color_pair(2))

    stats = f"{session_breaths} cycles  ·  {format_time(elapsed)}"
    draw_centered(stdscr, h // 2 + 1, stats, curses.color_pair(1))

    draw_centered(stdscr, h // 2 + 4, "press any key", curses.color_pair(4))

    stdscr.refresh()
    stdscr.nodelay(False)
    stdscr.getch()


def show_technique_menu(stdscr):
    """Show technique selection menu. Returns technique key."""
    curses.curs_set(0)
    selected = 0
    keys = list(TECHNIQUES.keys())

    while True:
        h, w = stdscr.getmaxyx()
        stdscr.erase()

        draw_centered(stdscr, 1, "B R E A T H E", curses.color_pair(5) | curses.A_BOLD)
        draw_centered(stdscr, 3, "choose your technique", curses.color_pair(2))

        for i, key in enumerate(keys):
            tech = TECHNIQUES[key]
            y = 6 + i * 2
            if y >= h - 3:
                break

            if i == selected:
                marker = "▸ "
                name_attr = curses.color_pair(5) | curses.A_BOLD
                desc_attr = curses.color_pair(1)
            else:
                marker = "  "
                name_attr = curses.color_pair(2)
                desc_attr = curses.color_pair(4)

            name_str = f"{marker}{tech['name']}"
            phases_str = "  " + " → ".join(
                f"{n} {d}s" for n, d in tech["phases"]
            )
            if tech.get("rounds"):
                phases_str += f"  ×{tech['rounds']} + hold {tech['hold_after']}s"

            draw_centered(stdscr, y, name_str, name_attr)
            draw_centered(stdscr, y + 1, tech["desc"], desc_attr)

        draw_centered(stdscr, h - 2, "↑↓ select  ⏎ start  q quit", curses.color_pair(4))

        stdscr.refresh()

        key = stdscr.getch()
        if key == curses.KEY_UP or key == ord('k'):
            selected = (selected - 1) % len(keys)
        elif key == curses.KEY_DOWN or key == ord('j'):
            selected = (selected + 1) % len(keys)
        elif key == ord('\n') or key == ord(' '):
            return keys[selected]
        elif key == ord('q') or key == 27:
            return None


# ─── Main Loop ────────────────────────────────────────────────────────
def main(stdscr):
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(50)

    # Parse args (already parsed globally, use the namespace)
    global args

    # ─── Colors ───────────────────────────────────────────────────
    curses.start_color()
    curses.use_default_colors()

    if curses.can_change_color():
        curses.init_color(10, 900, 600, 200)   # warm amber
        curses.init_color(11, 600, 400, 150)   # dim amber
        curses.init_color(12, 400, 250, 100)   # very dim
        curses.init_color(13, 200, 130, 50)    # ghost
        curses.init_color(14, 1000, 700, 300)  # bright amber
        curses.init_pair(1, 10, -1)
        curses.init_pair(2, 11, -1)
        curses.init_pair(3, 12, -1)
        curses.init_pair(4, 13, -1)
        curses.init_pair(5, 14, -1)
        curses.init_pair(6, curses.COLOR_GREEN, -1)
        curses.init_pair(7, curses.COLOR_RED, -1)
    else:
        curses.init_pair(1, curses.COLOR_YELLOW, -1)
        curses.init_pair(2, curses.COLOR_YELLOW, -1)
        curses.init_pair(3, curses.COLOR_WHITE, -1)
        curses.init_pair(4, curses.COLOR_WHITE, -1)
        curses.init_pair(5, curses.COLOR_YELLOW, -1)
        curses.init_pair(6, curses.COLOR_GREEN, -1)
        curses.init_pair(7, curses.COLOR_RED, -1)

    # ─── Technique selection ──────────────────────────────────────
    if args.technique:
        technique_key = args.technique
    elif not args.hook:
        stdscr.nodelay(False)
        technique_key = show_technique_menu(stdscr)
        if technique_key is None:
            return
        stdscr.nodelay(True)
        stdscr.timeout(50)
    else:
        technique_key = DEFAULT_TECHNIQUE

    engine = BreathEngine(technique_key)
    vertices, edges = SHAPES.get(technique_key, (CUBE_VERTICES, CUBE_EDGES))

    # ─── State ────────────────────────────────────────────────────
    h, w = stdscr.getmaxyx()
    start_time = time.time()
    last_claude_check = 0
    claude_status = "absent"
    was_claude_working = False
    angle_x = 0.0
    angle_y = 0.0
    session_breaths = 0
    last_phase = "rest"
    meditation_active = True
    timer_duration = args.timer * 60 if args.timer else None
    auto_end_claude = args.claude or args.hook
    particles = [Particle(w, h) for _ in range(NUM_PARTICLES)]
    end_reason = None
    sound_enabled = not args.silent
    last_phase_name = None

    while True:
        try:
            key = stdscr.getch()
        except:
            key = -1

        if key == ord('q') or key == 27:
            end_reason = "quit"
            break
        elif key == ord(' '):
            meditation_active = not meditation_active
        elif key == ord('r'):
            start_time = time.time()
            session_breaths = 0
        elif key == ord('s'):
            sound_enabled = not sound_enabled
        elif key == ord('t'):
            # Cycle through techniques
            keys = list(TECHNIQUES.keys())
            idx = keys.index(technique_key)
            technique_key = keys[(idx + 1) % len(keys)]
            engine = BreathEngine(technique_key)
            vertices, edges = SHAPES.get(technique_key, (CUBE_VERTICES, CUBE_EDGES))
            start_time = time.time()
            session_breaths = 0

        now = time.time()
        elapsed = now - start_time

        # ─── Timer check ─────────────────────────────────────────
        if timer_duration and elapsed >= timer_duration:
            end_reason = "timer"
            break

        # ─── Hook signal check ───────────────────────────────────
        if check_hook_signal():
            end_reason = "hook"
            break

        # ─── Claude status check ─────────────────────────────────
        if now - last_claude_check > CLAUDE_CHECK_INTERVAL:
            claude_status = detect_claude_status()
            last_claude_check = now

            if auto_end_claude:
                if claude_status == "working":
                    was_claude_working = True

                # Claude was working and now stopped or needs input
                if was_claude_working:
                    if claude_status == "waiting":
                        end_reason = "claude_input"
                        break
                    elif claude_status in ("idle", "absent"):
                        end_reason = "claude_done"
                        break

        # ─── Terminal size ────────────────────────────────────────
        h, w = stdscr.getmaxyx()
        if h < 10 or w < 40:
            stdscr.erase()
            safe_addstr(stdscr, 0, 0, "terminal too small", curses.color_pair(7))
            stdscr.refresh()
            time.sleep(0.1)
            continue

        # ─── Update ──────────────────────────────────────────────
        for p in particles:
            p.w = w
            p.h = h
            p.update()

        phase_name, progress, phase_dur = engine.get_phase(elapsed)

        # Count breaths
        if phase_name == "inhale" and last_phase != "inhale":
            session_breaths += 1
        last_phase = phase_name

        # Phase transition sound
        if sound_enabled and phase_name != last_phase_name and last_phase_name is not None:
            play_tick()
        last_phase_name = phase_name

        if meditation_active:
            angle_x += 0.008
            angle_y += 0.012

        stdscr.erase()

        # ─── Particles ───────────────────────────────────────────
        for p in particles:
            px, py = int(p.x), int(p.y)
            if 0 <= py < h - 1 and 0 <= px < w - 1:
                pair = 4 if p.life < 0.3 else (3 if p.life < 0.6 else 2)
                safe_addstr(stdscr, py, px, p.char, curses.color_pair(pair))

        # ─── 3D Shape ────────────────────────────────────────────
        cx = w // 2
        cy = h // 2 - 2

        # Shape breathes with you
        if phase_name == "inhale":
            scale = 3.0 + progress * 2.5
        elif phase_name == "hold":
            scale = 5.5 + math.sin(now * 2) * 0.2  # subtle pulse
        elif phase_name == "exhale":
            scale = 5.5 - progress * 2.5
        else:
            scale = 3.0

        projected = []
        for vx, vy, vz in vertices:
            rx, ry, rz = rotate_point(vx, vy, vz, angle_x, angle_y)
            sx, sy, f = project(rx, ry, rz, cx, cy, scale)
            projected.append((sx, sy, f))

        for e0, e1 in edges:
            x0, y0, f0 = projected[e0]
            x1, y1, f1 = projected[e1]
            points = draw_line_chars(x0, y0, x1, y1)
            avg_f = (f0 + f1) / 2
            for px, py in points:
                if 0 <= py < h - 1 and 0 <= px < w - 1:
                    if avg_f > 0.85:
                        ch, pair = '█', 1
                    elif avg_f > 0.7:
                        ch, pair = '▓', 1
                    elif avg_f > 0.55:
                        ch, pair = '░', 2
                    else:
                        ch, pair = '·', 3
                    safe_addstr(stdscr, py, px, ch, curses.color_pair(pair))

        for sx, sy, f in projected:
            if 0 <= sy < h - 1 and 0 <= sx < w - 1:
                safe_addstr(stdscr, sy, sx, '◆',
                           curses.color_pair(5) | curses.A_BOLD)

        # ─── Title + Technique ────────────────────────────────────
        title = "B R E A T H E"
        draw_centered(stdscr, 1, title, curses.color_pair(5) | curses.A_BOLD)
        draw_centered(stdscr, 2, engine.tech["name"],
                     curses.color_pair(2))

        # ─── Breath Guide ────────────────────────────────────────
        phase_labels = {
            "inhale":  "i n h a l e",
            "hold":    "h o l d",
            "exhale":  "e x h a l e",
            "rest":    "r e s t",
        }
        label = phase_labels.get(phase_name, phase_name)
        guide_y = h // 2 + 6

        bar_w = 24
        filled = int(progress * bar_w)
        bar = '━' * filled + '╸' + '─' * max(0, bar_w - filled - 1)

        draw_centered(stdscr, guide_y, label,
                     curses.color_pair(5) | curses.A_BOLD)
        draw_centered(stdscr, guide_y + 1, bar, curses.color_pair(2))

        # Round info (Wim Hof / Energy)
        round_info = engine.get_round_info()
        if round_info:
            draw_centered(stdscr, guide_y + 2, round_info,
                         curses.color_pair(3))

        # ─── Timer ────────────────────────────────────────────────
        timer_y = guide_y + 3
        if timer_duration:
            remaining = max(0, timer_duration - elapsed)
            time_label = f"◇ {format_time(remaining)}"
        else:
            time_label = f"◇ {format_time(elapsed)}"
        draw_centered(stdscr, timer_y, time_label, curses.color_pair(1))

        breath_str = f"{session_breaths} cycles"
        draw_centered(stdscr, timer_y + 1, breath_str, curses.color_pair(3))

        # ─── Claude Status ────────────────────────────────────────
        status_map = {
            "working": ("● claude is building", 6),
            "idle":    ("◌ claude is idle", 3),
            "waiting": ("◈ claude needs you", 5),
            "absent":  ("○ claude not detected", 4),
        }
        status_str, status_pair = status_map.get(claude_status, ("?", 4))

        draw_centered(stdscr, h - 4, status_str,
                     curses.color_pair(status_pair))

        if auto_end_claude:
            mode_str = "auto-end: on"
            draw_centered(stdscr, h - 3, mode_str, curses.color_pair(4))

        # ─── Controls ─────────────────────────────────────────────
        snd = "♪" if sound_enabled else "♪̸"
        controls = f"t·technique  s·sound{snd}  r·reset  q·quit"
        draw_centered(stdscr, h - 1, controls, curses.color_pair(4))

        if not meditation_active:
            draw_centered(stdscr, 4, "◆ P A U S E D ◆",
                         curses.color_pair(7) | curses.A_BOLD)

        stdscr.refresh()
        time.sleep(0.05)

    # ─── Session End ──────────────────────────────────────────────
    if end_reason:
        h, w = stdscr.getmaxyx()
        elapsed = time.time() - start_time
        if sound_enabled:
            show_completion_screen(stdscr, session_breaths, elapsed,
                                 end_reason, h, w)
        else:
            show_completion_screen.__wrapped__ = True
            # Still show screen, just no sound
            stdscr.erase()
            draw_centered(stdscr, h // 2 - 3,
                "◆  S E S S I O N   C O M P L E T E  ◆",
                curses.color_pair(5) | curses.A_BOLD)
            reasons = {
                "timer": "timer complete", "claude_done": "claude finished",
                "claude_input": "claude needs you", "hook": "hook signal",
                "quit": "session ended",
            }
            draw_centered(stdscr, h // 2 - 1,
                reasons.get(end_reason, end_reason), curses.color_pair(2))
            stats = f"{session_breaths} cycles  ·  {format_time(elapsed)}"
            draw_centered(stdscr, h // 2 + 1, stats, curses.color_pair(1))
            draw_centered(stdscr, h // 2 + 4, "press any key",
                         curses.color_pair(4))
            stdscr.refresh()
            stdscr.nodelay(False)
            stdscr.getch()


# ─── Hook Scripts ─────────────────────────────────────────────────────
def install_hooks():
    """Install Claude Code hooks for auto-meditation."""
    hooks_dir = os.path.expanduser("~/.claude/hooks")
    os.makedirs(hooks_dir, exist_ok=True)

    # Start hook: launches breathe in a new terminal
    start_script = f"""#!/bin/bash
# breathe: start meditation when Claude starts working
SCRIPT="{os.path.abspath(__file__)}"
PID_FILE="/tmp/breathe-session.pid"

# Don't start if already running
if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    exit 0
fi

# Launch in new Terminal window
osascript -e '
tell application "Terminal"
    activate
    set w to do script "python3 '\"$SCRIPT\"' --claude --technique focus; exit"
    set custom title of front window to "breathe"
end tell
' &

exit 0
"""

    # Stop hook: signal breathe to end
    stop_script = f"""#!/bin/bash
# breathe: signal meditation to end
touch /tmp/breathe-end-signal
exit 0
"""

    start_path = os.path.join(hooks_dir, "breathe-start.sh")
    stop_path = os.path.join(hooks_dir, "breathe-stop.sh")

    with open(start_path, 'w') as f:
        f.write(start_script)
    os.chmod(start_path, 0o755)

    with open(stop_path, 'w') as f:
        f.write(stop_script)
    os.chmod(stop_path, 0o755)

    # Now update settings.json
    settings_path = os.path.expanduser("~/.claude/settings.json")
    settings = {}
    if os.path.exists(settings_path):
        with open(settings_path) as f:
            settings = json.load(f)

    if "hooks" not in settings:
        settings["hooks"] = {}

    settings["hooks"]["PreToolUse"] = settings["hooks"].get("PreToolUse", [])
    settings["hooks"]["Stop"] = settings["hooks"].get("Stop", [])
    settings["hooks"]["Notification"] = settings["hooks"].get("Notification", [])

    # Check if our hooks already exist
    def has_breathe_hook(hook_list):
        for entry in hook_list:
            for h in entry.get("hooks", []):
                if "breathe" in h.get("command", ""):
                    return True
        return False

    if not has_breathe_hook(settings["hooks"]["PreToolUse"]):
        settings["hooks"]["PreToolUse"].append({
            "matcher": "Bash|Edit|Write",
            "hooks": [{
                "type": "command",
                "command": f"bash {start_path}",
            }]
        })

    if not has_breathe_hook(settings["hooks"]["Stop"]):
        settings["hooks"]["Stop"].append({
            "matcher": "",
            "hooks": [{
                "type": "command",
                "command": f"bash {stop_path}",
            }]
        })

    if not has_breathe_hook(settings["hooks"]["Notification"]):
        settings["hooks"]["Notification"].append({
            "matcher": "permission_prompt",
            "hooks": [{
                "type": "command",
                "command": f"bash {stop_path}",
            }]
        })

    print(f"\n  Hook scripts written to:")
    print(f"    {start_path}")
    print(f"    {stop_path}")
    print(f"\n  Settings to add to {settings_path}:")
    print(f"  (Review before applying)\n")
    print(json.dumps({"hooks": settings["hooks"]}, indent=2))
    print(f"\n  Run with --install-hooks --confirm to write settings.json")

    if "--confirm" in sys.argv:
        with open(settings_path, 'w') as f:
            json.dump(settings, f, indent=2)
        print(f"\n  ✓ Settings written to {settings_path}")
    print()


# ─── Entry ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="B R E A T H E — meditation for vibe coders",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--claude", action="store_true",
        help="Auto-end when Claude stops working or needs input")
    parser.add_argument("--hook", action="store_true",
        help="Hook mode: auto-end, no menu, clean exit")
    parser.add_argument("--timer", type=int, default=0,
        help="Timer in minutes (0 = infinite)")
    parser.add_argument("--technique", choices=list(TECHNIQUES.keys()),
        help="Breathing technique")
    parser.add_argument("--silent", action="store_true",
        help="No sound effects")
    parser.add_argument("--install-hooks", action="store_true",
        help="Install Claude Code hooks (prints config, use --confirm to apply)")

    args = parser.parse_args()

    if args.install_hooks:
        install_hooks()
        sys.exit(0)

    try:
        curses.wrapper(main)
        print("\n  namaste.\n")
    except KeyboardInterrupt:
        print("\n  namaste.\n")
