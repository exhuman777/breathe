#!/usr/bin/env python3
"""
  B R E A T H E
  meditation for vibe coders

  Two states:
    ACTIVE  → Claude is working. Your chosen mode plays (meditation or breathing).
    IDLE    → You're coding/prompting. Cozy ambient animation waits with you.

  On first launch: pick your mode (meditation timer or breathing technique).
  That mode replays every time Claude starts working.

  python3 breathe.py              # interactive setup
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

HOOK_SIGNAL_FILE = "/tmp/breathe-end-signal"
CLAUDE_CHECK_SEC = 2.0
NUM_PARTICLES = 16

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

def play_gong():
    try:
        for snd in ["/System/Library/Sounds/Glass.aiff"]:
            if os.path.exists(snd):
                subprocess.Popen(f'afplay "{snd}" && sleep 0.6 && afplay "{snd}" && sleep 0.9 && afplay "{snd}"',
                    shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); return
        print('\a', end='', flush=True)
    except: print('\a', end='', flush=True)

def play_tick():
    try: subprocess.Popen(['afplay','/System/Library/Sounds/Tink.aiff'],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except: pass

def play_alert():
    try:
        if os.path.exists("/System/Library/Sounds/Funk.aiff"):
            subprocess.Popen(['afplay','/System/Library/Sounds/Funk.aiff'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except: pass

def detect_claude():
    try:
        r = subprocess.run(['pgrep','-f','claude'], capture_output=True, text=True, timeout=2)
        if r.returncode != 0: return "absent"
        mx = 0.0
        for pid in (p for p in r.stdout.strip().split('\n') if p):
            try:
                ps = subprocess.run(['ps','-p',pid,'-o','%cpu='], capture_output=True, text=True, timeout=2)
                mx = max(mx, float(ps.stdout.strip()))
            except: pass
        if mx > 10: return "working"
        if mx > 2: return "idle"
        return "waiting"
    except: return "absent"

def check_hook():
    if os.path.exists(HOOK_SIGNAL_FILE):
        try: os.remove(HOOK_SIGNAL_FILE)
        except: pass
        return True
    return False

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

# ─── Setup Screen ─────────────────────────────────────────────────────
def setup_screen(stdscr, C):
    """First-time setup: pick mode + technique. Returns (mode, technique_key)."""
    curses.curs_set(0)
    sel_mode = 0   # 0 = breathing, 1 = meditation (timer only)
    sel_tech = 0
    tech_keys = list(TECHNIQUES.keys())
    step = 0  # 0 = pick mode, 1 = pick technique (if breathing)

    while True:
        h,w = stdscr.getmaxyx()
        stdscr.erase()

        ctr(stdscr, 1, "B R E A T H E", C[5] | curses.A_BOLD)
        ctr(stdscr, 2, "setup", C[2])

        if step == 0:
            ctr(stdscr, 5, "When Claude is building, what do you want?", C[5])

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
            ctr(stdscr, 5, "Pick your technique (press t to change later)", C[5])

            for i, k in enumerate(tech_keys):
                t = TECHNIQUES[k]
                y = 8 + i * 2
                if i == sel_tech:
                    ctr(stdscr, y, f"▸  {t['name']}   {t['short']}   {t['desc']}", C[5] | curses.A_BOLD)
                else:
                    ctr(stdscr, y, f"   {t['name']}   {t['short']}   {t['desc']}", C[2])

            ctr(stdscr, h-2, "↑↓  select    ⏎  confirm    ←  back", C[1] | curses.A_BOLD)

        stdscr.refresh()
        key = stdscr.getch()

        if key == ord('q') or key == 27:
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
                    step = 1  # pick technique
                else:
                    return "meditation", "focus"  # meditation uses focus shape
            else:
                return "breathing", tech_keys[sel_tech]
        elif key == curses.KEY_LEFT or key == ord('h'):
            if step == 1: step = 0


# ─── Main Loop ────────────────────────────────────────────────────────
def main(stdscr):
    global args
    curses.curs_set(0)
    stdscr.nodelay(False)
    stdscr.timeout(-1)

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

    # Setup
    if args.hook:
        user_mode, tech_key = "breathing", args.technique or "focus"
    elif args.technique:
        user_mode, tech_key = "breathing", args.technique
    else:
        user_mode, tech_key = setup_screen(stdscr, C)
        if user_mode is None: return

    engine = BreathEngine(tech_key)
    verts, edges = SHAPES[tech_key]
    tech_keys = list(TECHNIQUES.keys())
    tech_idx = tech_keys.index(tech_key)

    stdscr.nodelay(True); stdscr.timeout(50)

    h,w = stdscr.getmaxyx()
    t0 = time.time()
    last_cc = 0; cstat = "absent"
    ax = ay = 0.0
    breaths = 0; last_ph = ""; last_phn = None
    snd = not args.silent
    parts = [Particle(w,h) for _ in range(NUM_PARTICLES)]
    was_working = False; alert_done = False
    med_total = 0.0; med_start = None
    state = "idle"  # "idle" or "active"
    idle_t = 0
    # Idle animation: slow floating orb
    orb_phase = 0.0

    while True:
        try: key = stdscr.getch()
        except: key = -1

        if key == ord('q') or key == 27: break
        elif key == ord('t'):
            tech_idx = (tech_idx+1)%len(tech_keys)
            engine = BreathEngine(tech_keys[tech_idx])
            verts, edges = SHAPES[tech_keys[tech_idx]]
        elif key == ord('s'): snd = not snd

        now = time.time()
        if check_hook():
            if snd: play_gong()
            break

        # Claude check
        if now - last_cc > CLAUDE_CHECK_SEC:
            cstat = detect_claude()
            last_cc = now

            if cstat == "working":
                was_working = True
                if state != "active":
                    state = "active"; med_start = now; t0 = now
                    breaths = 0; alert_done = False
            elif was_working and cstat in ("waiting","absent","idle"):
                if state == "active":
                    med_total += now - (med_start or now)
                state = "idle"
                if not alert_done:
                    alert_done = True
                    if snd: play_alert()

        h,w = stdscr.getmaxyx()
        if h<10 or w<40:
            stdscr.erase(); sa(stdscr,0,0,"need 40x10",C[7]); stdscr.refresh()
            time.sleep(0.1); continue

        for p in parts: p.w,p.h=w,h; p.update()
        stdscr.erase()

        # Particles
        for p in parts:
            px,py=int(p.x),int(p.y)
            if 0<=py<h-1 and 0<=px<w-1:
                pc = C[4] if p.life<0.3 else (C[3] if p.life<0.6 else C[2])
                sa(stdscr,py,px,p.char,pc)

        ctr(stdscr, 0, "B R E A T H E", C[5]|curses.A_BOLD)

        # ══════════════════════════════════════════════════════════
        # ACTIVE: Claude is working → breathing or meditation
        # ══════════════════════════════════════════════════════════
        if state == "active":
            elapsed = now - t0

            # Always show 3D shape
            ax += 0.008; ay += 0.012
            ccx, ccy = w//2, h//2 - 3

            if user_mode == "breathing":
                pn, prog, pd = engine.get(elapsed)
                if pn=="inhale" and last_ph!="inhale": breaths+=1
                last_ph = pn
                if snd and pn!=last_phn and last_phn is not None: play_tick()
                last_phn = pn

                if pn=="inhale": sc=3.0+prog*2.5
                elif pn=="hold": sc=5.5+math.sin(now*2)*0.2
                elif pn=="exhale": sc=5.5-prog*2.5
                else: sc=3.0
            else:
                # Meditation: slow breathing geometry, no labels
                cycle = 10.0  # gentle 10s expand/contract
                prog = (math.sin(now * math.pi / (cycle/2)) + 1) / 2
                sc = 3.0 + prog * 2.5
                pn = None

            pr = []
            for vx,vy,vz in verts:
                rx,ry,rz = rot(vx,vy,vz,ax,ay)
                sx,sy,f = proj(rx,ry,rz,ccx,ccy,sc)
                pr.append((sx,sy,f))
            for e0,e1 in edges:
                x0,y0,f0=pr[e0]; x1,y1,f1=pr[e1]
                af=(f0+f1)/2
                for px,py in bres(x0,y0,x1,y1):
                    if 0<=py<h-1 and 0<=px<w-1:
                        if af>0.85: ch,cp='█',C[1]
                        elif af>0.7: ch,cp='▓',C[1]
                        elif af>0.55: ch,cp='░',C[2]
                        else: ch,cp='·',C[3]
                        sa(stdscr,py,px,ch,cp)
            for sx,sy,f in pr:
                if 0<=sy<h-1 and 0<=sx<w-1:
                    sa(stdscr,sy,sx,'◆',C[5]|curses.A_BOLD)

            # Mode-specific UI
            gy = h//2 + 4
            if user_mode == "breathing":
                tech = TECHNIQUES[tech_keys[tech_idx]]
                ctr(stdscr, 1, tech["name"], C[2])

                labels = {"inhale":"▲  I N H A L E  ▲","hold":"◆  H O L D  ◆",
                          "exhale":"▼  E X H A L E  ▼","rest":"·  R E S T  ·"}
                ctr(stdscr, gy, labels.get(pn,""), C[5]|curses.A_BOLD)

                bw = min(32, w-8)
                fl = int(prog * bw)
                bar = '━'*fl + '╸' + '─'*max(0,bw-fl-1)
                ctr(stdscr, gy+1, bar, C[1])

                if engine.rnds:
                    ctr(stdscr, gy+2, f"round {engine.rnd}/{engine.rnds}", C[2])

                ctr(stdscr, gy+3, f"◇ {fmt(elapsed)}  ·  {breaths} cycles", C[1])
            else:
                ctr(stdscr, 1, "M E D I T A T I O N", C[2])
                ctr(stdscr, gy+1, f"◇ {fmt(elapsed)}", C[1])

            ctr(stdscr, h-4, "● C L A U D E   I S   B U I L D I N G ●", C[6]|curses.A_BOLD)

        # ══════════════════════════════════════════════════════════
        # IDLE: You're coding. Cozy ambient.
        # ══════════════════════════════════════════════════════════
        else:
            idle_t += 1
            orb_phase += 0.02
            needs_action = was_working and cstat in ("waiting","absent")

            if needs_action:
                # Alert: action needed
                blink = (idle_t//8) % 2
                ctr(stdscr, 1, "◈ ◈ ◈  A C T I O N   N E E D E D  ◈ ◈ ◈",
                    C[7]|curses.A_BOLD if blink else C[5]|curses.A_BOLD)

                # Pulsing diamond
                ccx, ccy = w//2, h//2 - 1
                pulse = abs(math.sin(now * 3))
                r = 2 + pulse * 3
                for ang_i in range(4):
                    ang = ang_i * math.pi / 2 + math.pi / 4
                    px = int(ccx + math.cos(ang) * r * 2)
                    py = int(ccy + math.sin(ang) * r)
                    if 0<=py<h-1 and 0<=px<w-1:
                        sa(stdscr, py, px, '◆', C[7]|curses.A_BOLD if blink else C[5])

                sa(stdscr, ccy, ccx, '!', C[7]|curses.A_BOLD)

                if cstat == "waiting":
                    ctr(stdscr, h//2+3, "Claude needs your input", C[5]|curses.A_BOLD)
                else:
                    ctr(stdscr, h//2+3, "Claude finished", C[5]|curses.A_BOLD)
                ctr(stdscr, h//2+4, "switch to Claude Code", C[2])

                if med_total > 0:
                    ctr(stdscr, h//2+6, f"breathed {fmt(med_total)}  ·  {breaths} cycles", C[1])
            else:
                # Cozy idle: gentle orbiting dots, slow pulse
                ctr(stdscr, 1, "·  w a i t i n g  ·", C[3])

                # Floating orb constellation
                ccx, ccy = w//2, h//2 - 1
                num_orbs = 5
                for i in range(num_orbs):
                    angle = orb_phase + (i * 2 * math.pi / num_orbs)
                    r = 4 + math.sin(orb_phase * 0.3 + i) * 2
                    ox = int(ccx + math.cos(angle) * r * 2)
                    oy = int(ccy + math.sin(angle) * r)
                    if 0<=oy<h-1 and 0<=ox<w-1:
                        brightness = (math.sin(orb_phase + i * 1.2) + 1) / 2
                        if brightness > 0.7: sa(stdscr, oy, ox, '◆', C[5])
                        elif brightness > 0.4: sa(stdscr, oy, ox, '◇', C[1])
                        else: sa(stdscr, oy, ox, '·', C[2])

                # Center gentle pulse
                pulse = (math.sin(orb_phase * 0.5) + 1) / 2
                ch = '◆' if pulse > 0.5 else '◇'
                sa(stdscr, ccy, ccx, ch, C[5] if pulse > 0.5 else C[2])

                # Idle messages
                msgs = [
                    "energy follows attention",
                    "breathe between the builds",
                    "your companion is here",
                    "waiting for claude...",
                ]
                ctr(stdscr, h//2 + 4, msgs[(idle_t//160)%len(msgs)], C[3])

                # Status
                st_map = {"absent":"○ no claude","idle":"◌ claude idle","waiting":"◇ waiting"}
                ctr(stdscr, h-4, st_map.get(cstat,""), C[4])

        # Controls — always visible, bold
        tech = TECHNIQUES[tech_keys[tech_idx]]
        snd_s = "♪" if snd else "×"
        mode_s = "breath" if user_mode == "breathing" else "meditate"
        ctr(stdscr, h-2, f"[t] {tech['short']}  [s] {snd_s}  [q] quit  ·  {mode_s}", C[1]|curses.A_BOLD)
        sel = "  ".join(f"{'▸' if i==tech_idx else ' '}{k}" for i,k in enumerate(tech_keys))
        ctr(stdscr, h-1, sel, C[2])

        stdscr.refresh()
        time.sleep(0.05)


# ─── Hook Installer ───────────────────────────────────────────────────
def install_hooks():
    hd = os.path.expanduser("~/.claude/hooks"); os.makedirs(hd, exist_ok=True)
    sp = os.path.abspath(__file__)
    with open(f"{hd}/breathe-start.sh",'w') as f:
        f.write(f'#!/bin/bash\nLOCK="/tmp/breathe.lock"\nmkdir "$LOCK" 2>/dev/null || exit 0\n'
                f"osascript <<'AS' &\ntell application \"Terminal\"\n    activate\n"
                f"    do script \"python3 {sp} --hook; rm -rf /tmp/breathe.lock; exit\"\n"
                f"end tell\nAS\nexit 0\n")
    os.chmod(f"{hd}/breathe-start.sh", 0o755)
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
    print(json.dumps({"hooks":h}, indent=2))
    if "--confirm" in sys.argv:
        with open(sp_path,'w') as f: json.dump(s,f,indent=2)
        print(f"\nWritten to {sp_path}")
    else:
        print(f"\nAdd --confirm to apply to {sp_path}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="B R E A T H E")
    p.add_argument("--hook", action="store_true")
    p.add_argument("--technique", choices=list(TECHNIQUES.keys()))
    p.add_argument("--silent", action="store_true")
    p.add_argument("--install-hooks", action="store_true")
    args = p.parse_args()
    if args.install_hooks: install_hooks(); sys.exit(0)
    try: curses.wrapper(main); print("\n  namaste.\n")
    except KeyboardInterrupt: print("\n  namaste.\n")
