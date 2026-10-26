#!/usr/bin/env python3
"""mw_watchdog.py — MicrowareMobile (Redmi 9/MIUI) + DuckZilla (Moto G9/stock)
tunnel+adb watchdog (silent when healthy).

 It prints a message ONLY on a state change, per device:
   - tunnel UP -> DOWN   : alert + fix instructions
   - tunnel DOWN -> UP   : back-online notice
   - tunnel UP + adb lost: re-scan / adb connect by itself (port rotated), then report
 Healthy (tunnel up + adb up) -> empty stdout = silent, no disturbance

 Deploy: cp to ~/.hermes/scripts/mw_watchdog.py then register the cron
(no_agent=True, schedule "*/30 * * * *", deliver=origin)
"""
import json
import os
import re
import subprocess
import sys
import time

PHONES = [
    # (name, tunnel_ip, kind) kind: "miui" uses the skill's scan_connect | "stock" scans natively
    ("MicrowareMobile", "10.66.66.2", "miui"),
    ("DuckZilla", "10.66.66.3", "stock"),
]
STATE = os.path.expanduser("~/.hermes/state/mw_tun.json")
SCAN = os.path.expanduser(
    "~/.hermes/skills/devops/remote-phone-control/scripts/scan_connect.py")
STALE_H = 48


def sh(cmd, timeout=40):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout + r.stderr)
    except Exception as e:
        return 1, str(e)


def tunnel_up(ip):
    return sh(["ping", "-c2", "-W2", ip], timeout=20)[0] == 0


def adb_serial(ip):
    code, out = sh(["adb", "devices"], timeout=15)
    for ln in out.splitlines():
        m = re.match(rf"^({re.escape(ip)}:\d+)\s+device\s*$", ln.strip())
        if m:
            return m.group(1)
    return None


def scan_ports(ip):
    """Threaded scan of ports 1024-65535, then adb connect to each open port"""
    import socket
    import concurrent.futures

    def probe(p):
        s = socket.socket()
        s.settimeout(0.8)
        try:
            return p if s.connect_ex((ip, p)) == 0 else None
        finally:
            s.close()

    open_ports = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=800) as ex:
        for r in ex.map(probe, range(1024, 65536), chunksize=64):
            if r:
                open_ports.append(r)
    for p in sorted(open_ports):
        sh(["adb", "connect", f"{ip}:{p}"], timeout=15)
    return adb_serial(ip)


def adb_reconnect(ip, kind):
    if kind == "miui":
        code, out = sh(["python3", SCAN, ip], timeout=150)
        m = re.search(r"DEVICE:\s*(\S+)", out)
        return m.group(1) if m else None
    # stock: wireless-debug port rotates the same way — one native scan is enough
    ser = adb_serial(ip)
    if ser:
        return ser
    return scan_ports(ip)


def read_state():
    try:
        raw = open(STATE).read()
        if time.time() - os.path.getmtime(STATE) > STALE_H * 3600:
            return {}
        return json.loads(raw) if raw.strip() else {}
    except (OSError, ValueError):
        return {}


def write_state(st):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w") as f:
        json.dump(st, f)


def main():
    prev_all = read_state()
    st = dict(prev_all)
    msgs = []

    for name, ip, kind in PHONES:
        prev = prev_all.get(ip)
        up = tunnel_up(ip)
        if not up:  # ignore a short network blip
            time.sleep(8)
            up = tunnel_up(ip)
        cur = "up" if up else "down"

        if up:
            ser = adb_serial(ip)
            if not ser:
                ser = adb_reconnect(ip, kind)
                if ser:
                    msgs.append(f"🛰️ {name}: adb port rotated — reconnected for you: {ser}")
                else:
                    msgs.append(
                        f"⚠️ {name}: tunnel UP but no adb port found — if it just rebooted, "
                        f"the screen must be unlocked by hand once (Android rule)")
            st[ip] = "up" + (f" adb={ser}" if ser else " adb=none")
            if prev == "down":
                msgs.insert(0, f"✅ {name}: tunnel is back UP")
        else:
            st[ip] = "down"
            if prev != "down":
                extra = ("set battery = No restrictions + Always-on VPN"
                         if kind == "miui" else
                         "on stock Android this is rarer — open the WireGuard app on the device")
                msgs.append(
                    f"❌ {name} ({ip}): tunnel DOWN (ping fails)\n"
                    f"→ open the WireGuard app on the device and wait ~1 minute\n"
                    f"→ still DOWN: {extra}")

    write_state(st)
    if msgs:
        print("\n".join(msgs))
    sys.exit(0)


if __name__ == "__main__":
    main()
