#!/usr/bin/env python3
"""app_notifications.py — toggle per-app notifications on a phone reached over tunnel + wireless adb

Usage:
  app_notifications.py off  [--ip 10.66.66.2] [--apps shopee,tiktok,...] [pkg...]
  app_notifications.py on   [...]
  app_notifications.py status [...]

Examples (MicrowareMobile / Redmi 9):
  app_notifications.py off                      # shopee/tiktok/musically/lazada by default
  app_notifications.py on
  app_notifications.py status
  app_notifications.py off com.lazada.android   # explicit package only (overrides the keywords)

Mechanism: appops set <pkg> POST_NOTIFICATION ignore/allow (persists across reboot) +
best-effort pm revoke/grant android.permission.POST_NOTIFICATION —
on Android 12 pm revoke raises SecurityException (the permission is still "normal" there) and is skipped.

Requirements: WireGuard ON on the phone + wireless debugging enabled (it often stays on after an unlock)
"""
import argparse
import os
import re
import subprocess
import sys
import time

DEFAULT_APPS = "shopee,tiktok,musically,lazada"
SCAN_CONNECT = os.path.expanduser(
    "~/.hermes/skills/devops/remote-phone-control/scripts/scan_connect.py")


def run(cmd, timeout=60):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        r = subprocess.CompletedProcess(cmd, 124, "", "timeout")
        return r


def tunnel_up(ip):
    return run(["ping", "-c1", "-W2", ip]).returncode == 0


def connect_device(ip):
    for _ in range(3):
        if tunnel_up(ip):
            break
        time.sleep(3)
    else:
        print(f"TUNNEL DOWN: {ip} not responding — open the WireGuard app on the phone first, then rerun")
        sys.exit(2)
    r = run(["python3", SCAN_CONNECT, ip], timeout=120)
    m = re.search(r"DEVICE:\s*(\S+)", r.stdout)
    if not m:
        print("adb connect failed:\n" + (r.stdout + r.stderr).strip())
        print("→ no open port = wireless debugging needs one screen unlock first (post-reboot)")
        sys.exit(2)
    return m.group(1)


def adbsh(dev, cmd):
    return run(["adb", "-s", dev, "shell"] + cmd)


def find_packages(dev, filters):
    r = adbsh(dev, ["pm", "list", "packages", "-3"])
    pks = [ln.replace("package:", "").strip()
           for ln in r.stdout.splitlines() if ln.strip()]
    return sorted({p for p in pks if any(k in p.lower() for k in filters)})


def appop_state(dev, pkg):
    out = (adbsh(dev, ["appops", "get", pkg, "POST_NOTIFICATION"]).stdout +
           adbsh(dev, ["appops", "get", pkg, "POST_NOTIFICATION"]).stderr)
    low = out.lower()
    if "ignore" in low or "deny" in low:
        return "off"
    if "allow" in low:
        return "on"
    return "default"


def set_package(dev, pkg, mode):
    notes, ok = [], True
    val = "ignore" if mode == "off" else "allow"
    r = adbsh(dev, ["appops", "set", pkg, "POST_NOTIFICATION", val])
    if r.returncode == 0:
        notes.append(f"appops={val} ✓")
    else:
        ok = False
        notes.append("appops failed: " + (r.stderr or r.stdout).strip()[:80])

    perm = "android.permission.POST_NOTIFICATION"
    r = adbsh(dev, ["pm", "revoke", pkg, perm] if mode == "off"
              else ["pm", "grant", pkg, perm])
    if r.returncode == 0:
        notes.append("permission ✓")
    else:
        err = (r.stderr + r.stdout).lower()
        if "changeable" in err or "secur" in err or "unknown" in err:
            notes.append("permission=skipped")
        else:
            notes.append("permission=skipped: " + (r.stderr or r.stdout).strip()[:60])

    state = appop_state(dev, pkg)
    ok = ok and ((mode == "off" and state == "off") or (mode == "on" and state != "off"))
    return ok, f"-> {state} ({'; '.join(notes)})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["off", "on", "status"])
    ap.add_argument("pkgs", nargs="*", help="explicit packages (omit = discover via --apps)")
    ap.add_argument("--ip", default="10.66.66.2", help="tunnel IP of the device (default MicrowareMobile)")
    ap.add_argument("--apps", default=DEFAULT_APPS, help="comma-separated keywords used to discover packages")
    a = ap.parse_args()

    dev = connect_device(a.ip)
    print(f"DEVICE: {dev}")

    pks = a.pkgs or find_packages(dev, [k.strip() for k in a.apps.split(",") if k.strip()])
    if not pks:
        print(f"no apps matched: {a.pkgs or a.apps}")
        sys.exit(1)

    if a.mode == "status":
        for p in pks:
            print(f"{p:40s} {appop_state(dev, p)}")
        return

    label = "mute" if a.mode == "off" else "unmute"
    fails = 0
    for p in pks:
        ok, detail = set_package(dev, p, a.mode)
        print(f"{label} {p:40s} {detail}" + ("" if ok else "  ✗"))
        fails += 0 if ok else 1
    print("Result: " + ("all succeeded ✓" if not fails else f"{fails} item(s) need review"))
    sys.exit(0 if not fails else 3)


if __name__ == "__main__":
    main()
