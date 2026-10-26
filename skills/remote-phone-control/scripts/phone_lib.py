#!/usr/bin/env python3
"""Reusable helpers for Houston remote phone control (Redmi 9 / lancelot / MIUI 13).

Usage inside an inline heredoc script:
    import sys; sys.path.insert(0, '<skill_dir>/scripts')
    import phone_lib as pl
    dev = pl.bind()                 # pick_device + wire module globals
    pl.wake(); pl.cap('/tmp/x.png'); g = pl.detect_grid('/tmp/x.png')

Design rules baked in (see SKILL.md Golden Rules):
  * pick the adb port EVERY run (ports rotate; stale port = silent lies)
  * exec-out capture with size threshold (0B=transition, ~15KB=off, >100KB=content)
  * pixel-diff for effect verification (no-exception != working)
  * dense motionevent draw (never lift)
  * pattern read from vault at runtime, NEVER printed

Requires: pillow + numpy for detect_grid/pixel_diff
    python3 -m venv /tmp/pilenv && /tmp/pilenv/bin/pip install pillow numpy
"""
import subprocess, time, os, json, socket, concurrent.futures

PHONE_IP = "10.66.66.2"
PORT_RANGE = (1024, 65536)
LIT_MIN = 100000            # bytes => real content
VAULT = os.path.expanduser("~/.hermes/data/vault.json")
LOCK_ENTRY_PREFIX = "Phone Lock"

D = None                    # current device "ip:port"
ADB = ["adb"]

# ---------- device discovery ----------

def scan_open_ports(ip=PHONE_IP, workers=800):
    out = []
    def probe(p):
        s = socket.socket(); s.settimeout(1.0)
        try:
            if s.connect_ex((ip, p)) == 0: return p
        finally:
            s.close()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        for r in ex.map(probe, range(*PORT_RANGE), chunksize=64):
            if r: out.append(r)
    return sorted(out)

def pick_device():
    r = subprocess.run(["adb", "devices"], capture_output=True, text=True)
    for line in r.stdout.splitlines()[1:]:
        if line.startswith(PHONE_IP) and "\tdevice" in line:
            return line.split()[0]
    for p in scan_open_ports():
        subprocess.run(["adb", "connect", f"{PHONE_IP}:{p}"],
                       capture_output=True, timeout=15)
        r = subprocess.run(["adb", "devices"], capture_output=True, text=True)
        if f"{PHONE_IP}:{p}" in r.stdout and "\tdevice" in r.stdout.split(f"{PHONE_IP}:{p}")[1][:60]:
            return f"{PHONE_IP}:{p}"
    return None

def bind(retries=2):
    """Pick device and wire module globals. Returns device str or None."""
    global D, ADB
    for _ in range(retries):
        dev = pick_device()
        if dev:
            D = dev; ADB = ["adb", "-s", dev]
            return dev
        time.sleep(3)
    return None

# ---------- primitive shell ----------

def sh(*args, timeout=8):
    try:
        r = subprocess.run(ADB + ["shell"] + list(args),
                           capture_output=True, text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip()
    except Exception as e:
        return f"ERR {e}"

# ---------- state ----------

def state():
    w = "Awake" if "mWakefulness=Awake" in sh("dumpsys", "power") else "Asleep"
    s = "ON" if "mScreenState=ON" in sh("dumpsys", "display") else "OFF"
    return w, s

def focus():
    return sh("dumpsys", "window", "|", "grep", "mCurrentFocus")

def keyguard_up():
    f = focus()
    return "NotificationShade" in f or "systemui" in f.lower()

def lock_type():
    """'Pattern' / 'None' / unknown — from dumpsys lock_settings."""
    o = sh("dumpsys", "lock_settings")
    for line in o.splitlines():
        if "CredentialType" in line:
            return line.split(":", 1)[1].strip()
    return "?"

def probe_grant():
    """True if input injection is accepted (== SecurityException absent).
    NOTE: accepted != effective — verify with pixel_diff on a scrollable UI."""
    r = sh("input", "swipe", "500", "1800", "500", "1200", "200")
    return "SecurityException" not in r and "not found" not in r and "ERR" not in r

# ---------- capture / effects ----------

def cap(path, tries=5):
    """exec-out screencap. Returns bytes; >LIT_MIN means real content."""
    for _ in range(tries):
        try:
            with open(path, "wb") as f:
                subprocess.run(ADB + ["exec-out", "screencap", "-p"],
                               stdout=f, stderr=subprocess.PIPE, timeout=8)
            sz = os.path.getsize(path) if os.path.exists(path) else 0
            if sz > LIT_MIN:
                return sz
        except Exception:
            pass
        time.sleep(0.35)
    return os.path.getsize(path) if os.path.exists(path) else 0

def pixel_diff(a, b):
    """% changed pixels. >2 = real effect; ~0.16 = clock tick only."""
    import numpy as np
    from PIL import Image
    A = np.asarray(Image.open(a).convert("L"), dtype=np.int16)
    B = np.asarray(Image.open(b).convert("L"), dtype=np.int16)
    return 100.0 * (np.abs(A - B) > 12).mean()

# ---------- wake / keepalive ----------

def wake(tries=1):
    """Rotate wake methods (see matrix). Returns True if Awake."""
    if state()[0] == "Awake":
        return True
    for _ in range(tries):
        for fn in (
            lambda: sh("cmd", "notification", "post", "-S", "bigtext",
                       "-t", "Houston", "w", "go"),
            lambda: sh("am", "start", "-n",
                       "com.miui.calculator/.cal.CalculatorActivity"),
            lambda: sh("input", "keyevent", "26"),
        ):
            fn(); time.sleep(1.3)
            if state()[0] == "Awake":
                return True
    return False

def sleep_screen():
    """keyevent223 — only while grant open; creates a wake problem. Use sparingly."""
    r = sh("input", "keyevent", "223")
    return "SecurityException" not in r

# ---------- grid + pattern ----------

def detect_grid(image_path):
    """Return {digit:(x,y)} keypad-mapped or None. See references/grid-detect-and-draw.md."""
    from PIL import Image
    import numpy as np
    from collections import deque
    try:
        a = np.asarray(Image.open(image_path).convert("L"))
    except Exception:
        return None
    H, W = a.shape
    S = 3
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
                if visited[sy, sx]:
                    continue
                q = deque([(sy, sx)]); visited[sy, sx] = True; pts = []
                while q:
                    cy, cx = q.popleft(); pts.append((cy, cx))
                    if len(pts) > 900:
                        break
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = cy+dy, cx+dx
                            if 0 <= ny < hh and 0 <= nx < ww \
                                    and not visited[ny, nx] and mask[ny, nx]:
                                visited[ny, nx] = True; q.append((ny, nx))
                area = len(pts) * S * S
                if 100 <= area <= 7000:
                    comps.append((sum(p[1] for p in pts)/len(pts)*S + 40,
                                  sum(p[0] for p in pts)/len(pts)*S + y0))
            if len(comps) < 9:
                continue
            ys_sorted = sorted(c[1] for c in comps); rows = []
            for y in ys_sorted:
                if rows and y - rows[-1][-1] <= 90: rows[-1].append(y)
                else: rows.append([y])
            if len(rows) != 3:
                continue
            rc = [sum(r)/len(r) for r in rows]
            if not (110 <= rc[1]-rc[0] <= 450 and 110 <= rc[2]-rc[1] <= 450):
                continue
            by_row = {0: [], 1: [], 2: []}
            for (x, y) in comps:
                ri = min(range(3), key=lambda i: abs(rc[i]-y))
                if abs(rc[ri]-y) <= 90:
                    by_row[ri].append(x)
            gx, ok = {}, True
            for ri in (0, 1, 2):
                xs = sorted(by_row[ri])
                if len(xs) < 3: ok = False; break
                cl = []
                for x in xs:
                    if cl and x - cl[-1][-1] <= 90: cl[-1].append(x)
                    else: cl.append([x])
                if len(cl) != 3: ok = False; break
                gx[ri] = [sum(c)/len(c) for c in cl]
            if not ok:
                continue
            d1 = [gx[r][1]-gx[r][0] for r in (0,1,2)]
            d2 = [gx[r][2]-gx[r][1] for r in (0,1,2)]
            if max(d1)-min(d1) > 90 or max(d2)-min(d2) > 90:
                continue
            return {d: (round(gx[ri][ci]), round(rc[ri]))
                    for d, (ci, ri) in KEYPAD.items()}
    return None

def read_pattern():
    """Dash-ordered keypad pattern from vault. NEVER print or log it."""
    d = json.load(open(VAULT))
    for a in d.get("accounts", []):
        if a.get("site_name", "").startswith(LOCK_ENTRY_PREFIX):
            return a.get("password", "")
    return ""

def draw_pattern(grid, seq=None, step_sleep=0.045):
    """Dense continuous draw. Returns None on success or an error string.
    Aborts before sending anything if the pattern or a point is missing."""
    seq = (seq or read_pattern()).replace("-", "")
    if len(seq) != 7:
        return "PATTERN-MISSING"
    if not grid or any(c not in grid for c in seq):
        return "GRID-INCOMPLETE"
    pts = [grid[c] for c in seq]
    path = [pts[0]]
    for i in range(1, len(pts)):
        x0, y0 = pts[i-1]; x1, y1 = pts[i]
        for s in range(1, 7):
            path.append((round(x0 + (x1-x0)*s/6), round(y0 + (y1-y0)*s/6)))
    r = sh("input", "motionevent", "DOWN", str(path[0][0]), str(path[0][1]))
    if "SecurityException" in r:
        return "INJECT-BLOCKED"
    time.sleep(0.05)
    for (x, y) in path[1:]:
        sh("input", "motionevent", "MOVE", str(x), str(y))
        time.sleep(step_sleep)
    sh("input", "motionevent", "UP", str(path[-1][0]), str(path[-1][1]))
    return None

def unlock_chain(swipe_y=(2150, 1900, 2320), out_dir=os.path.expanduser("~")):
    """Wake -> raise bouncer -> detect -> draw -> verify. Returns status str."""
    if not bind():
        return "NO-DEVICE"
    if not probe_grant():
        return "GRANT-BLOCKED"
    if not wake():
        return "WAKE-FAILED"
    grid = None
    if keyguard_up():
        for ys in swipe_y:
            sh("input", "keyevent", "4"); sh("cmd", "statusbar", "collapse")
            time.sleep(0.25)
            sh("input", "swipe", "540", str(ys), "540", "700", "1000")
            time.sleep(0.35)
            p = os.path.join(out_dir, "chain_capture.png")
            if cap(p) > LIT_MIN:
                grid = detect_grid(p)
                if grid:
                    break
        if not grid:
            return "NO-GRID"
        err = draw_pattern(grid)
        if err:
            return err
        time.sleep(1.5)
    status = "UNLOCKED" if not keyguard_up() else "STILL-LOCKED"
    hp = os.path.join(out_dir, "unlocked_home.png")
    cap(hp)
    return status
