#!/usr/bin/env python3
"""show_rows.py - print a uiautomator dump XML as rows (text / content-desc / bounds).

    adb shell uiautomator dump /sdcard/u.xml && adb pull /sdcard/u.xml
    python3 show_rows.py u.xml
    python3 show_rows.py u.xml --badge
    python3 show_rows.py u.xml --bounds 500,1000
"""
import re
import sys
import html
import xml.etree.ElementTree as ET


def rows(path):
    root = ET.parse(path).getroot()
    out = []
    for n in root.iter("node"):
        t = (n.get("text") or "").strip()
        d = (n.get("content-desc") or "").strip()
        if not t and not d:
            continue
        b = n.get("bounds", "")
        m = re.findall(r"-?\d+", b)
        if len(m) == 4:
            cx = (int(m[0]) + int(m[2])) // 2
            cy = (int(m[1]) + int(m[3])) // 2
        else:
            cx = cy = -1
        out.append((cy, cx, html.unescape(t), html.unescape(d), b,
                    n.get("class", ""), n.get("clickable", "false")))
    out.sort()
    return out


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    path = sys.argv[1]
    badge = "--badge" in sys.argv
    pt = None
    if "--bounds" in sys.argv:
        i = sys.argv.index("--bounds")
        if i + 1 < len(sys.argv):
            pt = tuple(int(v) for v in sys.argv[i + 1].split(","))
    rs = rows(path)
    print(f"{len(rs)} rows with content ({path})")
    shown = 0
    for cy, cx, t, d, b, cls, click in rs:
        label = repr(t) + (f" desc={d!r}" if d and d != t else "")
        if badge and not re.search(r"\d+\s*new|unread|new items", t + " " + d, re.I):
            continue
        if pt:
            m = re.findall(r"-?\d+", b)
            if len(m) != 4 or not (int(m[0]) <= pt[0] <= int(m[2])
                                   and int(m[1]) <= pt[1] <= int(m[3])):
                continue
        print(" y=%5d x=%5d %s %s  [%s]"
              % (cy, cx, "*" if click == "true" else " ", label, cls.split(".")[-1]))
        shown += 1
    if badge or pt:
        print("-> %d matched" % shown)
    return 0


if __name__ == "__main__":
    sys.exit(main())
