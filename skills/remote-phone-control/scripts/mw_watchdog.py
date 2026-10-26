#!/usr/bin/env python3
"""mw_watchdog.py — MicrowareMobile (Redmi 9/MIUI) + DuckZilla (Moto G9/stock)
tunnel+adb watchdog (silent when healthy).

 พิมพ์ข้อความเฉพาะตอน "สถานะเปลี่ยน" เท่านั้น ต่อเครื่อง:
   - tunnel UP -> DOWN   : แจ้งเตือน + คำแนะนำ
   - tunnel DOWN -> UP   : แจ้งว่ากลับมาแล้ว
   - tunnel UP + adb หลุด : scan/adb connect ให้เอง (พอร์ตหมุน) แล้วรายงาน
 Healthy (tunnel up + adb up) -> stdout ว่าง = เงียบ ไม่รบกวน

 Deploy: cp ไป ~/.hermes/scripts/mw_watchdog.py แล้ว register cron
 (no_agent=True, schedule "*/30 * * * *", deliver=origin)
"""
import json
import os
import re
import subprocess
import sys
import time

PHONES = [
    # (name, tunnel_ip, kind) kind: "miui" ใช้ skill scan_connect | "stock" สแกนเอง
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
    """สแกนพอร์ต 1024-65535 แบบ thread แล้ว adb connect ทีละพอร์ต"""
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
        if not up:  # กันเน็ตสะดุดสั้นๆ
            time.sleep(8)
            up = tunnel_up(ip)
        cur = "up" if up else "down"

        if up:
            ser = adb_serial(ip)
            if not ser:
                ser = adb_reconnect(ip, kind)
                if ser:
                    msgs.append(f"🛰️ {name}: adb พอร์ตหมุน เรียกต่อให้แล้ว: {ser}")
                else:
                    msgs.append(
                        f"⚠️ {name}: tunnel UP แต่ adb สแกนไม่เจอพอร์ต — ถ้าเพิ่ง reboot "
                        f"ต้องปลดล็อกหน้าจอด้วยมือ 1 ครั้ง (กติกา Android)")
            st[ip] = "up" + (f" adb={ser}" if ser else " adb=none")
            if prev == "down":
                msgs.insert(0, f"✅ {name}: tunnel กลับมา UP แล้ว")
        else:
            st[ip] = "down"
            if prev != "down":
                extra = ("ตั้งแบตเตอรี่ = ไม่มีข้อจำกัด + Always-on VPN"
                         if kind == "miui" else
                         "stock Android น้อยกว่า ให้เปิดแอป WireGuard บนเครื่อง")
                msgs.append(
                    f"❌ {name} ({ip}): tunnel DOWN (ping ไม่เข้า)\n"
                    f"→ เปิดแอป WireGuard บนเครื่อง แล้วรอ ~1 นาที\n"
                    f"→ ยัง DOWN: {extra}")

    write_state(st)
    if msgs:
        print("\n".join(msgs))
    sys.exit(0)


if __name__ == "__main__":
    main()
