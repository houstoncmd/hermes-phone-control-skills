#!/usr/bin/env python3
"""phone_mission.py — remote phone control toolkit (remote-phone-control skill).

Usage: python3 phone_mission.py <scan|precheck|wake|grab OUT|grid OUT|unlock>

scan     : thread-scan open TCP ports on the phone via WireGuard tunnel + adb connect
precheck : inject-permission check (input keyevent 25 -> SecurityException?)
wake     : am-start wake, report wakefulness
grab OUT : wake + capture a lit frame (size oracle: 0=transition, 15197=off, >100k=lit)
grid OUT : detect the 3x3 pattern grid in a captured bouncer frame (keypad mapping)
unlock   : scan+connect -> wake -> slow swipe-up -> detect -> dense motionevent draw -> verify

Pattern is read from ~/.hermes/data/vault.json (site_name starts "Phone Lock") at runtime
and never printed. Import the helpers from other scripts via: import phone_mission as pm
"""
import sys, os, time, json, socket, subprocess, concurrent.futures
from collections import deque

TARGET = os.environ.get("PHONE_IP", "10.66.66.2")
ADB = ["adb", "-s", f"{TARGET}:0"]

def sh(*args, timeout=8):
    try:
        r = subprocess.run(ADB + ["shell"] + list(args), capture_output=True, text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip()
    except Exception as e:
        return f"ERR {e}"

def log(*a):
    print(*a, flush=True)

def wakeful():
    return "mWakefulness=Awake" in sh("dumpsys", "power")

def ensure_awake():
    if wakeful():
        return True
    sh("am", "start", "-n", "com.miui.calculator/.cal.CalculatorActivity")
    time.sleep(1.0)
    if not wakeful():
        sh("cmd", "notification", "post", "-S", "bigtext", "-t", "Houston", "w", "go")
        time.sleep(1.2)
    return wakeful()

def cap_exec(path, tries=5, awake_between=True):
    for _ in range(tries):
        if awake_between and not wakeful():
            ensure_awake()
        try:
            with open(path, "wb") as f:
                subprocess.run(ADB + ["exec-out", "screencap", "-p"], stdout=f,
                               stderr=subprocess.PIPE, timeout=8)
            sz = os.path.getsize(path) if os.path.exists(path) else 0
            if sz > 100000:
                return sz
        except Exception:
            pass
        time.sleep(0.4)
    return os.path.getsize(path) if os.path.exists(path) else 0

def scan_and_connect():
    out = []
    def probe(p):
        s = socket.socket(); s.settimeout(1.0)
        try:
            if s.connect_ex((TARGET, p)) == 0:
                return p
        finally:
            s.close()
    with concurrent.futures.ThreadPoolExecutor(max_workers=800) as ex:
        for r in ex.map(probe, range(1024, 65536), chunksize=64):
            if r:
                out.append(r)
    ports = sorted(out)
    log("OPEN:", ports)
    for p in ports:
        r = subprocess.run(["adb", "connect", f"{TARGET}:{p}"], capture_output=True, text=True, timeout=15)
        log(f"connect {p}:", (r.stdout + r.stderr).strip())
        if "connected" in (r.stdout + r.stderr):
            ADB[2] = f"{TARGET}:{p}"
            return p
    return None

def detect(path):
    """Detect 3x3 pattern grid -> {digit:(x,y)} keypad-mapped, else None."""
    import numpy as np
    from PIL import Image
    try:
        a = np.asarray(Image.open(path).convert("L"))
    except Exception as e:
        log("img-err", e); return None
    H, W = a.shape; S = 3
    KEYPAD = {"1": (0,0), "2": (1,0), "3": (2,0),
              "4": (0,1), "5": (1,1), "6": (2,1),
              "7": (0,2), "8": (1,2), "9": (2,2)}
    for thr in (160, 135, 110):
        for y0 in (1150, 1400):
            y1 = min(2200, H)
            mask = (a[y0:y1, 40:W-40] > thr)[::S, ::S]
            hh, ww = mask.shape
            visited = np.zeros_like(mask, dtype=bool)
            comps = []
            ys_i, xs_i = np.nonzero(mask)
            for sy, sx in zip(ys_i.tolist(), xs_i.tolist()):
                if visited[sy, sx]: continue
                q = deque([(sy, sx)]); visited[sy, sx] = True; pts = []
                while q:
                    cy, cx = q.popleft(); pts.append((cy, cx))
                    if len(pts) > 900: break
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = cy+dy, cx+dx
                            if 0 <= ny < hh and 0 <= nx < ww and not visited[ny, nx] and mask[ny, nx]:
                                visited[ny, nx] = True; q.append((ny, nx))
                area = len(pts) * S * S
                if 100 <= area <= 7000:
                    comps.append((sum(p[1] for p in pts)/len(pts)*S + 40,
                                  sum(p[0] for p in pts)/len(pts)*S + y0))
            if len(comps) < 9: continue
            ys_sorted = sorted(c[1] for c in comps); rows = []
            for y in ys_sorted:
                if rows and y - rows[-1][-1] <= 90: rows[-1].append(y)
                else: rows.append([y])
            if len(rows) != 3: continue
            rc = [sum(r)/len(r) for r in rows]
            if not (110 <= rc[1]-rc[0] <= 450 and 110 <= rc[2]-rc[1] <= 450): continue
            by_row = {0: [], 1: [], 2: []}
            for (x, y) in comps:
                ri = min(range(3), key=lambda i: abs(rc[i]-y))
                if abs(rc[ri]-y) <= 90: by_row[ri].append(x)
            gx = {}; ok = True
            for ri in (0, 1, 2):
                xs = sorted(by_row[ri])
                if len(xs) < 3: ok = False; break
                cl = []
                for x in xs:
                    if cl and x - cl[-1][-1] <= 90: cl[-1].append(x)
                    else: cl.append([x])
                if len(cl) != 3: ok = False; break
                gx[ri] = [sum(c)/len(c) for c in cl]
            if not ok: continue
            d1 = [gx[r][1]-gx[r][0] for r in (0,1,2)]
            d2 = [gx[r][2]-gx[r][1] for r in (0,1,2)]
            if max(d1)-min(d1) > 90 or max(d2)-min(d2) > 90: continue
            return {d: (round(gx[ri][ci]), round(rc[ri])) for d, (ci, ri) in KEYPAD.items()}
    return None

def read_pattern():
    d = json.load(open(os.path.expanduser("~/.hermes/data/vault.json")))
    for a in d.get("accounts", []):
        if a.get("site_name", "").startswith("Phone Lock"):
            return a.get("password", "").replace("-", "")
    return ""

def draw_pattern(grid, seq):
    """Dense continuous motionevent gesture through pattern points (6 substeps/segment)."""
    pts = [grid[c] for c in seq]
    path = [pts[0]]
    for i in range(1, len(pts)):
        x0, y0 = pts[i-1]; x1, y1 = pts[i]
        for s in range(1, 7):
            path.append((round(x0+(x1-x0)*s/6), round(y0+(y1-y0)*s/6)))
    r = sh("input", "motionevent", "DOWN", str(path[0][0]), str(path[0][1]))
    if "SecurityException" in r:
        return "INJECT-BLOCKED"
    time.sleep(0.05)
    for (x, y) in path[1:]:
        sh("input", "motionevent", "MOVE", str(x), str(y)); time.sleep(0.045)
    sh("input", "motionevent", "UP", str(path[-1][0]), str(path[-1][1]))
    return None

def cmd_unlock():
    if not scan_and_connect():
        log("RESULT: NOT-CONNECTED"); return 2
    ensure_awake()
    for ys in (2150, 1900, 2320):
        sh("input", "keyevent", "4"); sh("cmd", "statusbar", "collapse"); time.sleep(0.25)
        sh("input", "swipe", "540", str(ys), "540", "700", "1000")   # slow ~1s drag
        time.sleep(0.4)
        sz = cap_exec("/tmp/bouncer.png")
        if sz > 100000:
            g = detect("/tmp/bouncer.png")
            log(f"[swipe-{ys}] {sz}B {'GRID' if g else 'no-grid'}")
            if g:
                log("[grid]", json.dumps(g))
                seq = read_pattern()
                if len(seq) != 7:
                    log("RESULT: PATTERN-MISSING"); return 4
                err = draw_pattern(g, seq)
                if err:
                    log("RESULT:", err); return 5
                time.sleep(1.2)
                focus = sh("dumpsys", "window", "|", "grep", "mCurrentFocus")
                log("[focus]", focus)
                sz2 = cap_exec("/tmp/home.png")
                log("[home]", sz2, "B")
                unlocked = "NotificationShade" not in focus and "systemui" not in focus.lower()
                log("RESULT:", "UNLOCKED" if unlocked else "STILL-LOCKED")
                return 0 if unlocked else 6
    log("RESULT: NO-GRID"); return 3

def main():
    if len(sys.argv) < 2:
        print(__doc__); return 1
    c = sys.argv[1]
    if c == "scan":
        p = scan_and_connect()
        log(subprocess.run(["adb", "devices", "-l"], capture_output=True, text=True).stdout)
        return 0 if p else 2
    if c == "precheck":
        if not scan_and_connect(): return 2
        r = sh("input", "keyevent", "25")
        log("INJECT:", "BLOCKED" if "SecurityException" in r else "OPEN")
        return 0
    if c == "wake":
        if not scan_and_connect(): return 2
        log("awake:", ensure_awake()); return 0
    if c == "grab":
        if not scan_and_connect(): return 2
        sz = cap_exec(sys.argv[2])
        log("grabbed:", sz, "B ->", sys.argv[2])
        return 0 if sz > 100000 else 3
    if c == "grid":
        g = detect(sys.argv[2])
        log("grid:", json.dumps(g) if g else "NONE")
        return 0 if g else 3
    if c == "unlock":
        return cmd_unlock()
    print(__doc__)
    return 1

if __name__ == "__main__":
    sys.exit(main())
