#!/usr/bin/env python3
"""Detect the 3x3 Android pattern-view dot grid in a phone screenshot.

Usage:  python3 find_pattern_grid.py <screenshot.png> [out_grid.json]

Needs Pillow (this box: /tmp/pilenv/bin/python, recreate with
`python3 -m venv /tmp/pilenv && /tmp/pilenv/bin/pip install pillow`).

Prints keypad-mapped coordinates (rows top->bottom = 1-2-3 / 4-5-6 / 7-8-9)
and writes JSON {"<keypad digit>": [x, y], ...} to out_grid.json (default /tmp/grid.json).

Heuristic: bright connected blobs (threshold tries 150/175/200) in y 950-2320,
clustered into exactly 3 rows (y-gap < 80) and 3 columns per row (x-gap < 80).
Non-grid screens (notifications text, bottom shortcuts) fail the 3x3 test safely.
"""
import sys, json
from collections import deque

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow missing: python3 -m venv /tmp/pilenv && /tmp/pilenv/bin/pip install pillow")

path = sys.argv[1]
out = sys.argv[2] if len(sys.argv) > 2 else "/tmp/grid.json"
im = Image.open(path).convert("L")
W, H = im.size
px = im.load()

def blobs(thr, y0=950, y1=2320, min_a=120, max_a=5000):
    visited = bytearray(W * H); res = []
    for y in range(y0, y1, 2):
        for x in range(20, W - 20, 2):
            i = y * W + x
            if visited[i] or px[x, y] < thr:
                continue
            q = deque([(x, y)]); visited[i] = 1; pts = []
            while q:
                cx, cy = q.popleft(); pts.append((cx, cy))
                for dx, dy in ((2, 0), (-2, 0), (0, 2), (0, -2)):
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < W and y0 <= ny < y1:
                        j = ny * W + nx
                        if not visited[j] and px[nx, ny] >= thr:
                            visited[j] = 1; q.append((nx, ny))
            a = len(pts) * 4
            if min_a <= a <= max_a:
                res.append((sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)))
    return res

def grid_from(res):
    if len(res) < 9:
        return None, f"blobs={len(res)}"
    ys = sorted(p[1] for p in res); rows = []
    for y in ys:
        if rows and y - rows[-1][-1] < 80:
            rows[-1].append(y)
        else:
            rows.append([y])
    if len(rows) != 3:
        return None, f"blobs={len(res)} rows={len(rows)}"
    rc = [sum(r) / len(r) for r in rows]
    cols = {}
    for x, y in res:
        ri = min(range(3), key=lambda i: abs(rc[i] - y))
        cols.setdefault(ri, []).append(x)
    out_cols = {}
    for ri in sorted(cols):
        xs = sorted(cols[ri]); cl = []
        for x in xs:
            if cl and x - cl[-1][-1] < 80:
                cl[-1].append(x)
            else:
                cl.append([x])
        if len(cl) != 3:
            return None, f"rows=3 but row{ri} cols={len(cl)}"
        out_cols[ri] = [round(sum(c) / len(c)) for c in cl]
    if len(out_cols) != 3:
        return None, "incomplete rows"
    # keypad digits: row0 (top) = 1,2,3 ; row1 = 4,5,6 ; row2 = 7,8,9
    g = {}
    for ri in range(3):
        for ci in range(3):
            g[str(ri * 3 + ci + 1)] = [out_cols[ri][ci], round(rc[ri])]
    return g, None

for thr in (150, 175, 200):
    g, err = grid_from(blobs(thr))
    if g:
        json.dump(g, open(out, "w"))
        print("GRID", json.dumps(g))
        print("saved ->", out)
        sys.exit(0)
    print(f"thr={thr}: {err}")

print("NO_GRID (screen is not showing the pattern view — check screenshot manually)")
sys.exit(1)
