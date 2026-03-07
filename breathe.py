#!/usr/bin/env python3
"""
  b r e A I t h
  meditation + journal for vibe coders

  Single instance. Launch once, stays open.

  States:
    SETUP   -> pick mode (breathing or meditation) + technique
    IDLE    -> ambient starfield. waiting for Claude.
    ACTIVE  -> Claude is building. your mode plays.
    JOURNAL -> gong. write your thoughts or skip.

  python3 breathe.py                          # launch (once, stays open)
  python3 breathe.py --install-hooks --confirm # install Claude Code hooks
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

# ─── Breathing Techniques ─────────────────────────────────────────────
TECHNIQUES = {
    "box":    {"name": "B O X",    "desc": "stress control",  "short": "4-4-4-4",
               "phases": [("inhale",4),("hold",4),("exhale",4),("hold",4)]},
    "relax":  {"name": "R E L A X","desc": "deep relaxation", "short": "4-7-8",
               "phases": [("inhale",4),("hold",7),("exhale",8)]},
    "focus":  {"name": "F O C U S","desc": "clarity breath",  "short": "4-4-6-2",
               "phases": [("inhale",4),("hold",4),("exhale",6),("rest",2)]},
    "energy": {"name": "E N E R G Y","desc": "activation",    "short": "fast+hold",
               "phases": [("inhale",1.5),("exhale",1.0)],
               "rounds": 20, "hold_after": 15},
}

# ─── 3D Shapes ────────────────────────────────────────────────────────
CUBE_V = [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]
CUBE_E = [(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7)]
OCT_V  = [(0,-1,0),(1,0,0),(0,0,1),(-1,0,0),(0,0,-1),(0,1,0)]
OCT_E  = [(0,1),(0,2),(0,3),(0,4),(5,1),(5,2),(5,3),(5,4),(1,2),(2,3),(3,4),(4,1)]
TET_V  = [(1,1,1),(1,-1,-1),(-1,1,-1),(-1,-1,1)]
TET_E  = [(0,1),(0,2),(0,3),(1,2),(1,3),(2,3)]
SHAPES = {"box":(CUBE_V,CUBE_E),"relax":(OCT_V,OCT_E),"focus":(CUBE_V,CUBE_E),"energy":(TET_V,TET_E)}

MED_STYLES = ["wireframe", "sacred", "lissajous"]

HOOK_START_FILE = "/tmp/breathe-start-signal"
HOOK_END_FILE   = "/tmp/breathe-end-signal"
SESSION_ACTIVE_FILE = "/tmp/breathe-session-active"
CLAUDE_CHECK_SEC = 3.0
START_CONFIRM_SEC = 2.0    # wait 2s after first signal, then confirm before activating
END_CONFIRM_COUNT = 3      # need 3 consecutive "not active" checks to end
END_CHECK_INTERVAL = 2.0   # seconds between end-confirmation checks
NUM_PARTICLES = 30
JSONL_DIR = os.path.expanduser("~/.claude/projects")
JSONL_SCAN_INTERVAL = 30.0  # rescan for newest JSONL every 30s
JSONL_THINKING_SEC = 8.0    # modified within 8s = actively working
JSONL_EXISTS_SEC = 60.0     # modified within 60s = session exists
BREAITH_DIR  = os.path.expanduser("~/.breaith")
CONFIG_PATH  = os.path.join(BREAITH_DIR, "config.json")
JOURNAL_PATH = os.path.join(BREAITH_DIR, "journal.md")

# ─── Helpers ──────────────────────────────────────────────────────────
class Particle:
    def __init__(s, w, h):
        s.w, s.h = w, h; s.respawn(True)
    def update(s):
        s.x += s.vx; s.y += s.vy; s.life -= 0.002
        if s.life <= 0 or s.y < 0 or s.x < 0 or s.x >= s.w: s.respawn()
    def respawn(s, init=False):
        s.x = random.randint(0, max(1,s.w-1))
        s.y = random.randint(0, max(1,s.h-1)) if init else s.h-1
        s.vx = (random.random()-0.5)/6; s.vy = -random.random()/10 - 0.015
        s.life = random.random() if init else 1.0
        s.char = random.choice(['·','∘','·','·','˙'])

def play_deep_gong():
    """Layered deep meditation gong. Two Glass.aiff voices at different pitches."""
    try:
        snd = "/System/Library/Sounds/Glass.aiff"
        if os.path.exists(snd):
            # Primary: very deep, slow
            subprocess.Popen(['afplay', '-r', '0.35', snd],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # Overtone: slightly higher, delayed 0.15s via lighter rate
            subprocess.Popen(['afplay', '-r', '0.5', snd],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        print('\a', end='', flush=True)
    except: print('\a', end='', flush=True)

def play_tick():
    try: subprocess.Popen(['afplay','/System/Library/Sounds/Tink.aiff'],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except: pass

def check_start_signal():
    if os.path.exists(HOOK_START_FILE):
        try: os.remove(HOOK_START_FILE)
        except: pass
        return True
    return False

def check_end_signal():
    if os.path.exists(HOOK_END_FILE):
        try: os.remove(HOOK_END_FILE)
        except: pass
        return True
    return False

_jsonl_cache = {"path": None, "mtime": 0, "scan_time": 0}

def _find_newest_jsonl():
    """Find the most recently modified .jsonl transcript in Claude projects dir."""
    newest, newest_mt = None, 0
    try:
        for proj in os.listdir(JSONL_DIR):
            proj_path = os.path.join(JSONL_DIR, proj)
            if not os.path.isdir(proj_path):
                continue
            try:
                for f in os.listdir(proj_path):
                    if f.endswith('.jsonl') and f != 'history.jsonl':
                        fp = os.path.join(proj_path, f)
                        try:
                            mt = os.stat(fp).st_mtime
                            if mt > newest_mt:
                                newest_mt = mt
                                newest = fp
                        except OSError:
                            pass
            except OSError:
                pass
    except OSError:
        pass
    return newest, newest_mt

def claude_cpu_check():
    """Detect Claude Code activity. Returns 'thinking', 'exists', or 'absent'.

    Zero-subprocess detection:
    1. /tmp/breathe-session-active — from SessionStart/SessionEnd hooks
    2. JSONL file mtime — Claude writes transcripts during work
    No pgrep/ps subprocess spawning.
    """
    now = time.time()
    c = _jsonl_cache

    # Layer 1: session lifecycle file (from hooks)
    session_exists = os.path.exists(SESSION_ACTIVE_FILE)

    # Layer 2: JSONL transcript activity
    # Periodically rescan for the newest JSONL file
    if c["path"] is None or (now - c["scan_time"]) > JSONL_SCAN_INTERVAL:
        c["path"], c["mtime"] = _find_newest_jsonl()
        c["scan_time"] = now

    jsonl_age = None
    if c["path"]:
        try:
            current_mt = os.stat(c["path"]).st_mtime
            if current_mt != c["mtime"]:
                c["mtime"] = current_mt
                # File changed — rescan in case a newer session started
                c["path"], c["mtime"] = _find_newest_jsonl()
                c["scan_time"] = now
            jsonl_age = now - c["mtime"]
        except OSError:
            c["path"] = None  # file gone, rescan next cycle

    # Decision: combine both signals
    if session_exists and jsonl_age is not None and jsonl_age < JSONL_THINKING_SEC:
        return "thinking"  # session active + fresh writes = working
    if jsonl_age is not None and jsonl_age < JSONL_THINKING_SEC:
        return "thinking"  # fresh writes even without session file
    if session_exists:
        return "exists"    # session alive but no recent writes
    if jsonl_age is not None and jsonl_age < JSONL_EXISTS_SEC:
        return "exists"    # recent-ish activity
    return "absent"

def rot(x,y,z,ax,ay):
    ca,sa=math.cos(ax),math.sin(ax); y2,z2=y*ca-z*sa,y*sa+z*ca
    cb,sb=math.cos(ay),math.sin(ay); return x*cb+z2*sb, y2, -x*sb+z2*cb

def proj(x,y,z,cx,cy,sc):
    f=4.0/(4.0+z); return int(cx+x*sc*f*2), int(cy+y*sc*f), f

def bres(x0,y0,x1,y1):
    pts=[]; dx,dy=abs(x1-x0),abs(y1-y0)
    sx,sy=(1 if x0<x1 else -1),(1 if y0<y1 else -1); err=dx-dy
    for _ in range(500):
        pts.append((x0,y0))
        if x0==x1 and y0==y1: break
        e2=2*err
        if e2>-dy: err-=dy; x0+=sx
        if e2<dx: err+=dx; y0+=sy
    return pts

class BreathEngine:
    def __init__(s,key):
        s.tech=TECHNIQUES[key]; s.phases=s.tech["phases"]
        s.cycle=sum(d for _,d in s.phases)
        s.rnds=s.tech.get("rounds"); s.hold=s.tech.get("hold_after"); s.rnd=0
    def get(s,t):
        if s.rnds and s.hold:
            rt=s.rnds*s.cycle; cp=t%(rt+s.hold)
            if cp<rt: s.rnd=int(cp/s.cycle)+1; return s._at(cp%s.cycle)
            return ("hold",(cp-rt)/s.hold,s.hold)
        return s._at(t%s.cycle)
    def _at(s,p):
        for n,d in s.phases:
            if p<d: return (n,p/d,d)
            p-=d
        n,d=s.phases[-1]; return (n,1.0,d)

def fmt(s): return f"{int(s)//60:02d}:{int(s)%60:02d}"

def sa(scr,y,x,t,a=0):
    h,w=scr.getmaxyx()
    if 0<=y<h and 0<=x<w:
        try: scr.addnstr(y,x,t,w-x-1,a)
        except: pass

def ctr(scr,y,t,a=0):
    _,w=scr.getmaxyx(); sa(scr,y,max(0,(w-len(t))//2),t,a)

def load_config():
    try:
        with open(CONFIG_PATH) as f: return json.load(f)
    except: return None

def save_config(mode, technique, med_style=None):
    try:
        os.makedirs(BREAITH_DIR, exist_ok=True)
        d = {"mode": mode, "technique": technique}
        if med_style is not None:
            d["med_style"] = med_style
        with open(CONFIG_PATH, 'w') as f:
            json.dump(d, f)
    except: pass

def save_journal_entry(text, duration, breaths):
    try:
        os.makedirs(BREAITH_DIR, exist_ok=True)
        with open(JOURNAL_PATH, 'a') as f:
            ts = time.strftime("%Y-%m-%d %H:%M")
            f.write(f"\n---\n**{ts}**  ·  {fmt(duration)}  ·  {breaths} breaths\n\n{text}\n")
    except: pass

# ─── Setup Screen (Main Menu) ────────────────────────────────────────
def setup_screen(stdscr, C):
    """Pick mode + technique. Returns (mode, tech_key) or (None, None) to quit."""
    curses.curs_set(0)
    stdscr.nodelay(False)
    stdscr.timeout(-1)
    sel_mode = 0
    sel_tech = 0
    tech_keys = list(TECHNIQUES.keys())
    step = 0

    while True:
        h,w = stdscr.getmaxyx()
        stdscr.erase()

        ctr(stdscr, 1, "b r e A I t h", C[5] | curses.A_BOLD)
        ctr(stdscr, 2, "setup", C[2])

        if step == 0:
            ctr(stdscr, 5, "when claude is building, what do you want?", C[5])
            opts = [
                ("B R E A T H I N G", "guided breathing technique with 3D visuals"),
                ("M E D I T A T I O N", "silent timer. just the geometry and you."),
            ]
            for i, (name, desc) in enumerate(opts):
                y = 8 + i * 3
                if i == sel_mode:
                    ctr(stdscr, y, f"▸  {name}", C[5] | curses.A_BOLD)
                    ctr(stdscr, y+1, desc, C[1])
                else:
                    ctr(stdscr, y, f"   {name}", C[2])
                    ctr(stdscr, y+1, desc, C[4])
            ctr(stdscr, h-2, "↑↓  select    ⏎  confirm    q  quit", C[1] | curses.A_BOLD)

        elif step == 1:
            ctr(stdscr, 5, "pick your technique (press t to change later)", C[5])
            for i, k in enumerate(tech_keys):
                t = TECHNIQUES[k]
                y = 8 + i * 2
                if i == sel_tech:
                    ctr(stdscr, y, f"▸  {t['name']}   {t['short']}   {t['desc']}", C[5] | curses.A_BOLD)
                else:
                    ctr(stdscr, y, f"   {t['name']}   {t['short']}   {t['desc']}", C[2])
            ctr(stdscr, h-2, "↑↓  select    ⏎  confirm    ←  back    q  quit", C[1] | curses.A_BOLD)

        stdscr.refresh()
        key = stdscr.getch()

        if key == ord('q'):
            return None, None
        elif key == curses.KEY_UP or key == ord('k'):
            if step == 0: sel_mode = (sel_mode - 1) % 2
            else: sel_tech = (sel_tech - 1) % len(tech_keys)
        elif key == curses.KEY_DOWN or key == ord('j'):
            if step == 0: sel_mode = (sel_mode + 1) % 2
            else: sel_tech = (sel_tech + 1) % len(tech_keys)
        elif key == ord('\n') or key == ord(' '):
            if step == 0:
                if sel_mode == 0:
                    step = 1
                else:
                    return "meditation", "focus"
            else:
                return "breathing", tech_keys[sel_tech]
        elif key == curses.KEY_LEFT or key == ord('h'):
            if step == 1: step = 0


# ─── Journal Screen ──────────────────────────────────────────────────
def journal_screen(stdscr, C, duration, breaths):
    """Post-meditation thought capture. Enter saves, Esc skips."""
    curses.curs_set(1)
    stdscr.nodelay(False)
    stdscr.timeout(-1)
    text = []

    while True:
        h, w = stdscr.getmaxyx()
        stdscr.erase()

        ctr(stdscr, 1, "b r e A I t h", C[5] | curses.A_BOLD)
        ctr(stdscr, 3, f"◇ {fmt(duration)}  ·  {breaths} breaths", C[1])
        ctr(stdscr, 5, "any thoughts from the silence?", C[5])

        # Text input box
        max_w = min(60, w - 6)
        start_x = max(2, (w - max_w) // 2)
        input_y = 8

        sa(stdscr, input_y - 1, start_x - 1, "┌" + "─" * max_w + "┐", C[2])
        for row in range(3):
            sa(stdscr, input_y + row, start_x - 1, "│", C[2])
            sa(stdscr, input_y + row, start_x, " " * max_w, C[2])
            sa(stdscr, input_y + row, start_x + max_w, "│", C[2])
        sa(stdscr, input_y + 3, start_x - 1, "└" + "─" * max_w + "┘", C[2])

        # Render text with wrapping
        txt = "".join(text)
        lines = []
        for i in range(0, max(1, len(txt) + 1), max(1, max_w)):
            lines.append(txt[i:i+max_w])
        if not lines:
            lines = [""]

        for i, line in enumerate(lines[:3]):
            sa(stdscr, input_y + i, start_x, line, C[5])

        # Position cursor
        cur_line = min(len(lines) - 1, 2)
        cur_col = len(lines[cur_line]) if cur_line < len(lines) else 0
        try:
            stdscr.move(input_y + cur_line, start_x + cur_col)
        except: pass

        ctr(stdscr, h - 3, "⏎  save    esc  skip", C[1] | curses.A_BOLD)

        stdscr.refresh()
        ch = stdscr.getch()

        if ch == 27:  # Esc = skip
            curses.curs_set(0)
            return ""
        elif ch in (10, curses.KEY_ENTER):  # Enter = save
            curses.curs_set(0)
            return "".join(text).strip()
        elif ch in (127, 8, curses.KEY_BACKSPACE):
            if text: text.pop()
        elif 32 <= ch <= 126:
            if len(text) < max_w * 3:
                text.append(chr(ch))

    curses.curs_set(0)
    return ""


# ─── Main Loop ────────────────────────────────────────────────────────
def main(stdscr):
    global args
    curses.curs_set(0)
    curses.start_color(); curses.use_default_colors()
    if curses.can_change_color():
        curses.init_color(10,900,600,200); curses.init_color(11,600,400,150)
        curses.init_color(12,400,250,100); curses.init_color(13,200,130,50)
        curses.init_color(14,1000,700,300); curses.init_color(15,300,900,400)
        curses.init_color(16,900,300,300)
        for i,c in enumerate([10,11,12,13,14,15,16],1): curses.init_pair(i,c,-1)
    else:
        for i,c in enumerate([curses.COLOR_YELLOW]*2+[curses.COLOR_WHITE]*2+
                             [curses.COLOR_YELLOW,curses.COLOR_GREEN,curses.COLOR_RED],1):
            curses.init_pair(i,c,-1)
    C = {i: curses.color_pair(i) for i in range(1,8)}

    # ── Resolve mode: CLI flag > saved config > setup screen ──
    config = load_config()
    if args.technique:
        user_mode, tech_key = "breathing", args.technique
        save_config(user_mode, tech_key)
    elif config and config.get("mode") and config.get("technique"):
        user_mode = config["mode"]
        tech_key = config["technique"]
    else:
        user_mode, tech_key = setup_screen(stdscr, C)
        if user_mode is None: return
        save_config(user_mode, tech_key)

    # Meditation style index (persisted)
    med_style_idx = 0
    if config and config.get("med_style") in MED_STYLES:
        med_style_idx = MED_STYLES.index(config["med_style"])

    engine = BreathEngine(tech_key)
    verts, edges = SHAPES[tech_key]
    tech_keys = list(TECHNIQUES.keys())
    tech_idx = tech_keys.index(tech_key)

    stdscr.nodelay(True); stdscr.timeout(50)

    h,w = stdscr.getmaxyx()
    t0 = time.time()
    ax = ay = 0.0
    breaths = 0; last_ph = ""; last_phn = None
    snd = not args.silent
    parts = [Particle(w,h) for _ in range(NUM_PARTICLES)]
    was_working = False
    med_total = 0.0; med_start = None
    state = "idle"
    idle_t = 0
    orb_phase = 0.0
    last_activity = 0
    last_cpu_check = 0
    start_signal_time = 0      # when first start evidence appeared
    start_from_hook = False    # True if activation triggered by hook (trusted)
    end_idle_count = 0         # consecutive "not thinking" checks
    last_end_check = 0         # last end-confirmation check timestamp

    # Clean stale signals
    for f in [HOOK_START_FILE, HOOK_END_FILE]:
        try: os.remove(f)
        except: pass

    while True:
        try: key = stdscr.getch()
        except: key = -1

        now = time.time()

        # ── Quit ──
        if key == ord('q'): break

        # ── Arrow back / Esc → main menu (from idle or active) ──
        go_setup = False
        if key in (curses.KEY_LEFT, ord('h')) and state in ("idle", "active"):
            go_setup = True
        if key == 27 and state == "active":
            go_setup = True

        if go_setup:
            if state == "active" and med_start:
                med_total += now - med_start
                med_start = None
            user_mode, tech_key = setup_screen(stdscr, C)
            if user_mode is None: break
            save_config(user_mode, tech_key)
            engine = BreathEngine(tech_key)
            verts, edges = SHAPES[tech_key]
            tech_idx = tech_keys.index(tech_key)
            med_style_idx = 0
            state = "idle"
            was_working = False
            idle_t = 0
            start_signal_time = 0; start_from_hook = False; end_idle_count = 0; last_end_check = 0
            stdscr.nodelay(True); stdscr.timeout(50)
            for f in [HOOK_START_FILE, HOOK_END_FILE]:
                try: os.remove(f)
                except: pass
            continue

        # ── Technique / sound toggle ──
        if key == ord('t') and state in ("idle", "active"):
            if user_mode == "breathing":
                tech_idx = (tech_idx+1) % len(tech_keys)
                tech_key = tech_keys[tech_idx]
                engine = BreathEngine(tech_key)
                verts, edges = SHAPES[tech_key]
                save_config(user_mode, tech_key)
            else:
                med_style_idx = (med_style_idx + 1) % len(MED_STYLES)
                save_config(user_mode, tech_key, MED_STYLES[med_style_idx])
        if key == ord('s'):
            snd = not snd

        # ══════ ACTIVATION: hooks + JSONL file monitoring ══════

        hook_triggered = check_start_signal()
        if hook_triggered:
            last_activity = now
            if state == "active":
                end_idle_count = 0
            elif start_signal_time == 0:
                start_signal_time = now
                start_from_hook = True

        if state == "idle" and now - last_cpu_check > CLAUDE_CHECK_SEC:
            last_cpu_check = now
            cpu = claude_cpu_check()
            if cpu == "thinking":
                last_activity = now
                if start_signal_time == 0:
                    start_signal_time = now
                    start_from_hook = False

        # Confirm start after debounce delay
        if state == "idle" and start_signal_time > 0 and (now - start_signal_time) >= START_CONFIRM_SEC:
            if start_from_hook or claude_cpu_check() == "thinking":
                state = "active"; med_start = now; t0 = now
                breaths = 0; last_ph = ""; last_phn = None
                was_working = True
                end_idle_count = 0; last_end_check = 0
            start_signal_time = 0

        # ══════ DEACTIVATION: debounced end → GONG + JOURNAL ══════

        # Trigger end-confirmation sequence on end signal or timeout
        end_hook_received = check_end_signal()
        if end_hook_received and state == "active":
            end_idle_count = max(end_idle_count, 1)  # start counting
            last_end_check = 0  # force immediate check

        if state == "active" and (now - last_activity) > 12:
            if end_idle_count == 0:
                end_idle_count = 1  # start end-confirmation sequence
                last_end_check = 0  # force immediate first check

        # Debounced end-confirmation: check every END_CHECK_INTERVAL
        if state == "active" and end_idle_count > 0 and (now - last_end_check) >= END_CHECK_INTERVAL:
            last_end_check = now
            cpu = claude_cpu_check()
            if cpu == "thinking":
                # Still working — reset counter, refresh activity timer
                end_idle_count = 0
                last_activity = now
            else:
                end_idle_count += 1

        end_session = state == "active" and end_idle_count >= END_CONFIRM_COUNT

        if end_session:
            session_dur = now - (med_start or now)
            med_total += session_dur
            med_start = None
            session_breaths = breaths
            start_signal_time = 0

            # Deep gong
            if snd: play_deep_gong()

            # Journal
            text = journal_screen(stdscr, C, session_dur, session_breaths)
            if text:
                save_journal_entry(text, session_dur, session_breaths)

            state = "idle"
            idle_t = 0
            end_idle_count = 0; last_end_check = 0
            stdscr.nodelay(True); stdscr.timeout(50)
            continue

        # ══════ RENDER ══════

        h,w = stdscr.getmaxyx()
        if h < 10 or w < 40:
            stdscr.erase(); sa(stdscr,0,0,"need 40x10",C[7]); stdscr.refresh()
            time.sleep(0.1); continue

        for p in parts: p.w,p.h=w,h; p.update()
        stdscr.erase()

        # Particles (always)
        for p in parts:
            px,py = int(p.x), int(p.y)
            if 0<=py<h-1 and 0<=px<w-1:
                pc = C[4] if p.life<0.3 else (C[3] if p.life<0.6 else C[2])
                sa(stdscr,py,px,p.char,pc)

        ctr(stdscr, 0, "b r e A I t h", C[5]|curses.A_BOLD)

        # ══════ ACTIVE STATE ══════
        if state == "active":
            elapsed = now - t0
            ax += 0.008; ay += 0.012
            ccx, ccy = w//2, h//2 - 3

            if user_mode == "breathing":
                pn, prog, pd = engine.get(elapsed)
                if pn == "inhale" and last_ph != "inhale": breaths += 1
                last_ph = pn
                if snd and pn != last_phn and last_phn is not None: play_tick()
                last_phn = pn
                if pn == "inhale": sc = 3.0 + prog * 2.5
                elif pn == "hold": sc = 5.5 + math.sin(now*2) * 0.2
                elif pn == "exhale": sc = 5.5 - prog * 2.5
                else: sc = 3.0
            else:
                # Meditation: gentle expand/contract
                cycle = 10.0
                prog = (math.sin(now * math.pi / (cycle/2)) + 1) / 2
                sc = 3.0 + prog * 2.5
                pn = None

            # ── Visual dispatch ──
            draw_wireframe = (user_mode == "breathing") or (med_style_idx == 0)

            if draw_wireframe:
                # 3D shape
                pr = []
                for vx,vy,vz in verts:
                    rx,ry,rz = rot(vx,vy,vz,ax,ay)
                    sx,sy,f = proj(rx,ry,rz,ccx,ccy,sc)
                    pr.append((sx,sy,f))
                for e0,e1 in edges:
                    x0,y0,f0 = pr[e0]; x1,y1,f1 = pr[e1]
                    af = (f0+f1)/2
                    for px,py in bres(x0,y0,x1,y1):
                        if 0<=py<h-1 and 0<=px<w-1:
                            if af>0.85: ch,cp = '█',C[1]
                            elif af>0.7: ch,cp = '▓',C[1]
                            elif af>0.55: ch,cp = '░',C[2]
                            else: ch,cp = '·',C[3]
                            sa(stdscr,py,px,ch,cp)
                for sx,sy,f in pr:
                    if 0<=sy<h-1 and 0<=sx<w-1:
                        sa(stdscr,sy,sx,'◆',C[5]|curses.A_BOLD)

            elif med_style_idx == 1:
                # ── Sacred Geometry: flower of life + aurora ──
                # Flower of life: 7 circles (center + 6 hex positions)
                fol_r = min(h//4, w//8)
                rot_ang = now * 0.15
                centers = [(0, 0)]
                for i in range(6):
                    a = math.pi / 3 * i + rot_ang
                    centers.append((math.cos(a) * fol_r, math.sin(a) * fol_r))
                for ci, (ox, oy) in enumerate(centers):
                    n_pts = 24
                    for j in range(n_pts):
                        a = 2 * math.pi * j / n_pts + rot_ang
                        px = int(ccx + (ox + math.cos(a) * fol_r) * 2)
                        py = int(ccy + oy + math.sin(a) * fol_r)
                        if 0 <= py < h - 1 and 0 <= px < w - 1:
                            depth = (math.sin(now * 0.8 + ci + j * 0.3) + 1) / 2
                            if depth > 0.6: sa(stdscr, py, px, '◇', C[5])
                            elif depth > 0.3: sa(stdscr, py, px, '·', C[1])
                            else: sa(stdscr, py, px, '˙', C[2])
                # Center jewel
                sa(stdscr, ccy, ccx, '◆', C[5] | curses.A_BOLD)

                # Aurora: 3 sine wave bands across upper area
                for band in range(3):
                    band_y = 3 + band * 2
                    freq = 0.08 + band * 0.03
                    phase = now * (0.6 + band * 0.4)
                    bc = [C[6], C[5], C[1]][band]
                    for x in range(2, w - 2):
                        dy = math.sin(x * freq + phase) * 1.5
                        ry = int(band_y + dy)
                        if 0 <= ry < h - 1:
                            brightness = (math.sin(x * 0.15 + phase * 1.3) + 1) / 2
                            ch = '~' if brightness > 0.5 else '·'
                            sa(stdscr, ry, x, ch, bc)

            elif med_style_idx == 2:
                # ── Lissajous: orbit ring particles + parametric trail ──
                # Orbit rings: 3 rings of 8 particles each
                for ring in range(3):
                    r = 4 + ring * 3
                    speed = 0.5 + ring * 0.3
                    tilt = ring * 0.4
                    rc = [C[5], C[1], C[2]][ring]
                    rch = '◇' if ring == 0 else '·'
                    for i in range(8):
                        a = 2 * math.pi * i / 8 + now * speed
                        ox = math.cos(a) * r * 2
                        oy = math.sin(a) * r * math.cos(tilt)
                        oz = math.sin(a) * r * math.sin(tilt)
                        # simple depth fade
                        f = 1.0 + oz * 0.1
                        px = int(ccx + ox * f)
                        py = int(ccy + oy * f)
                        if 0 <= py < h - 1 and 0 <= px < w - 1:
                            sa(stdscr, py, px, rch, rc | curses.A_BOLD)

                # Lissajous trail: x=sin(at+d), y=sin(bt)
                n_trail = 60
                a_ratio = 3 + math.sin(now * 0.1) * 0.5
                b_ratio = 2
                delta = now * 0.3
                lr = min(h // 3, w // 6)
                for i in range(n_trail):
                    t_param = i * 0.12
                    lx = math.sin(a_ratio * t_param + delta)
                    ly = math.sin(b_ratio * t_param)
                    px = int(ccx + lx * lr * 2)
                    py = int(ccy + ly * lr)
                    if 0 <= py < h - 1 and 0 <= px < w - 1:
                        age = i / n_trail
                        if age < 0.3: sa(stdscr, py, px, '◆', C[5] | curses.A_BOLD)
                        elif age < 0.6: sa(stdscr, py, px, '◇', C[1])
                        else: sa(stdscr, py, px, '·', C[2])

            # Mode UI
            gy = h//2 + 4
            if user_mode == "breathing":
                tech = TECHNIQUES[tech_keys[tech_idx]]
                ctr(stdscr, 1, tech["name"], C[2])
                labels = {"inhale":"▲  I N H A L E  ▲", "hold":"◆  H O L D  ◆",
                          "exhale":"▼  E X H A L E  ▼", "rest":"·  R E S T  ·"}
                ctr(stdscr, gy, labels.get(pn,""), C[5]|curses.A_BOLD)
                bw = min(32, w-8)
                fl = int(prog * bw)
                bar = '━'*fl + '╸' + '─'*max(0,bw-fl-1)
                ctr(stdscr, gy+1, bar, C[1])
                if engine.rnds:
                    ctr(stdscr, gy+2, f"round {engine.rnd}/{engine.rnds}", C[2])
                ctr(stdscr, gy+3, f"◇ {fmt(elapsed)}  ·  {breaths} cycles", C[1])
            else:
                style_name = MED_STYLES[med_style_idx]
                ctr(stdscr, 1, f"M E D I T A T I O N  ·  {style_name}", C[2])
                ctr(stdscr, gy+1, f"◇ {fmt(elapsed)}", C[1])

            ctr(stdscr, h-4, "● C L A U D E   I S   B U I L D I N G ●", C[6]|curses.A_BOLD)
            if user_mode == "breathing":
                ctr(stdscr, h-2, f"[t] {TECHNIQUES[tech_key]['short']}  [s] {'♪' if snd else '×'}  [←] menu  [q] quit", C[1]|curses.A_BOLD)
            else:
                ctr(stdscr, h-2, f"[t] {MED_STYLES[med_style_idx]}  [s] {'♪' if snd else '×'}  [←] menu  [q] quit", C[1]|curses.A_BOLD)

        # ══════ IDLE STATE ══════
        elif state == "idle":
            idle_t += 1
            orb_phase += 0.02

            # After 2 min idle, fade from "your turn" to ambient
            if was_working and idle_t < 2400:
                ctr(stdscr, 1, "◇  y o u r   t u r n  ◇", C[5])
                ccx, ccy = w//2, h//2 - 1
                pulse = (math.sin(now * 1.2) + 1) / 2
                for ring in range(3):
                    r = 3 + ring * 2.5 + pulse * 1.5
                    n_pts = 6 + ring * 2
                    for i in range(n_pts):
                        ang = (2*math.pi*i/n_pts) + now * 0.3 * (1 + ring*0.5)
                        px = int(ccx + math.cos(ang) * r * 2)
                        py = int(ccy + math.sin(ang) * r)
                        if 0<=py<h-1 and 0<=px<w-1:
                            depth = (ring + 1) / 3
                            if depth > 0.7: sa(stdscr, py, px, '◇', C[5])
                            elif depth > 0.4: sa(stdscr, py, px, '·', C[1])
                            else: sa(stdscr, py, px, '˙', C[2])
                sa(stdscr, ccy, ccx, '◆', C[5])
                ctr(stdscr, h//2+3, "claude is waiting for you", C[1])
                ctr(stdscr, h//2+4, "switch back when ready", C[3])
                if med_total > 0:
                    ctr(stdscr, h//2+6, f"breathed {fmt(med_total)}  ·  total", C[1])
            else:
                if was_working: was_working = False  # fade complete
                ctr(stdscr, 1, "·  w a i t i n g  ·", C[3])
                ccx, ccy = w//2, h//2 - 1

                # Deep background stars
                random.seed(42)
                for i in range(25):
                    sx = random.randint(1, w-2)
                    sy = random.randint(2, h-4)
                    twinkle = math.sin(now * 0.5 + i * 2.7)
                    if twinkle > 0.3:
                        ch = '·' if twinkle < 0.7 else '∘'
                        sa(stdscr, sy, sx, ch, C[4] if twinkle < 0.7 else C[3])
                random.seed()

                # Mid orbiting constellation
                for i in range(7):
                    ang = orb_phase * 0.4 + (i * 2 * math.pi / 7)
                    r = 6 + math.sin(orb_phase * 0.2 + i) * 2
                    ox = int(ccx + math.cos(ang) * r * 2)
                    oy = int(ccy + math.sin(ang) * r)
                    if 0<=oy<h-1 and 0<=ox<w-1:
                        b = (math.sin(orb_phase * 0.6 + i * 1.5) + 1) / 2
                        if b > 0.6: sa(stdscr, oy, ox, '◇', C[1])
                        elif b > 0.3: sa(stdscr, oy, ox, '·', C[2])
                        else: sa(stdscr, oy, ox, '˙', C[3])

                # Close orbiting ring
                for i in range(5):
                    ang = orb_phase * 0.8 + (i * 2 * math.pi / 5) + math.pi/4
                    r = 3 + math.sin(orb_phase * 0.5 + i * 0.8) * 1
                    ox = int(ccx + math.cos(ang) * r * 2)
                    oy = int(ccy + math.sin(ang) * r)
                    if 0<=oy<h-1 and 0<=ox<w-1:
                        b = (math.sin(orb_phase + i * 1.2) + 1) / 2
                        if b > 0.5: sa(stdscr, oy, ox, '◆', C[5])
                        else: sa(stdscr, oy, ox, '◇', C[1])

                # Center pulse
                pulse = (math.sin(orb_phase * 0.3) + 1) / 2
                sa(stdscr, ccy, ccx, '◆' if pulse > 0.5 else '◇',
                   C[5] if pulse > 0.5 else C[2])

                msgs = [
                    "energy follows attention",
                    "breathe between the builds",
                    "your companion is here",
                    "waiting for claude...",
                ]
                ctr(stdscr, h//2 + 4, msgs[(idle_t//160)%len(msgs)], C[3])

                # Claude status
                if idle_t % 60 == 0:
                    main._ce = claude_cpu_check() != "absent"
                has_claude = getattr(main, '_ce', False)
                st = "◌ claude idle" if has_claude else "○ no claude"
                ctr(stdscr, h-4, st, C[4])

            # Idle controls
            if user_mode == "breathing":
                ctr(stdscr, h-2, f"[t] {TECHNIQUES[tech_key]['short']}  [s] {'♪' if snd else '×'}  [←] menu  [q] quit  ·  breath", C[1]|curses.A_BOLD)
                sel = "  ".join(f"{'▸' if i==tech_idx else ' '}{k}" for i,k in enumerate(tech_keys))
                ctr(stdscr, h-1, sel, C[2])
            else:
                ctr(stdscr, h-2, f"[t] {MED_STYLES[med_style_idx]}  [s] {'♪' if snd else '×'}  [←] menu  [q] quit  ·  meditate", C[1]|curses.A_BOLD)
                sel = "  ".join(f"{'▸' if i==med_style_idx else ' '}{s}" for i,s in enumerate(MED_STYLES))
                ctr(stdscr, h-1, sel, C[2])

        stdscr.refresh()
        time.sleep(0.05)


# ─── Hook Installer ───────────────────────────────────────────────────
def install_hooks():
    hd = os.path.expanduser("~/.claude/hooks"); os.makedirs(hd, exist_ok=True)
    # Start hook: just touch signal file. No Terminal launch.
    with open(f"{hd}/breathe-start.sh",'w') as f:
        f.write("#!/bin/bash\ntouch /tmp/breathe-start-signal\nexit 0\n")
    os.chmod(f"{hd}/breathe-start.sh", 0o755)
    # Stop hook: just touch signal file.
    with open(f"{hd}/breathe-stop.sh",'w') as f:
        f.write("#!/bin/bash\ntouch /tmp/breathe-end-signal\nexit 0\n")
    os.chmod(f"{hd}/breathe-stop.sh", 0o755)

    sp_path = os.path.expanduser("~/.claude/settings.json")
    s = {}
    if os.path.exists(sp_path):
        with open(sp_path) as f: s = json.load(f)
    h = s.get("hooks",{})
    def has(l): return any("breathe" in x.get("command","") for e in l for x in e.get("hooks",[]))
    for ev in ["PreToolUse","Stop","Notification"]: h.setdefault(ev,[])
    if not has(h["PreToolUse"]):
        h["PreToolUse"].append({"matcher":"Bash|Edit|Write","hooks":[{"type":"command","command":f"bash {hd}/breathe-start.sh","async":True}]})
    if not has(h["Stop"]):
        h["Stop"].append({"matcher":"","hooks":[{"type":"command","command":f"bash {hd}/breathe-stop.sh"}]})
    if not has(h["Notification"]):
        h["Notification"].append({"matcher":"permission_prompt","hooks":[{"type":"command","command":f"bash {hd}/breathe-stop.sh"}]})
    s["hooks"] = h
    with open(sp_path,'w') as f: json.dump(s,f,indent=2)
    print(f"Hooks written to {sp_path}")
    print(json.dumps({"hooks":h}, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="b r e A I t h — meditation + journal")
    p.add_argument("--technique", choices=list(TECHNIQUES.keys()), help="Start with technique")
    p.add_argument("--silent", action="store_true", help="No sound")
    p.add_argument("--install-hooks", action="store_true", help="Install Claude Code hooks")
    p.add_argument("--confirm", action="store_true")
    p.add_argument("--hook", action="store_true", help=argparse.SUPPRESS)  # legacy, ignored
    args = p.parse_args()
    if args.install_hooks: install_hooks(); sys.exit(0)
    try: curses.wrapper(main); print("\n  namaste.\n")
    except KeyboardInterrupt: print("\n  namaste.\n")
