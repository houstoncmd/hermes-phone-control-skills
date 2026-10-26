#!/usr/bin/env python3
"""scan_connect.py — find the phone's rotating wireless-debug ports and adb-connect them.

Usage: python3 scan_connect.py [phone_tunnel_ip]
Prints OPEN ports, adb connect results, and the connected device (or exits 1).
Run this whenever `adb devices` shows no10.66.66.2 entry (ports rotate on every
wireless-debug re-init / reboot; pairing usually survives).
"""
import socket, concurrent.futures, subprocess, sys, time

TARGET = sys.argv[1] if len(sys.argv) > 1 else "10.66.66.2"

def scan():
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
    return sorted(out)

def adb_devices():
    r = subprocess.run(["adb", "devices"], capture_output=True, text=True)
    return [l.split()[0] for l in r.stdout.splitlines()[1:]
            if l.strip() and l.strip().endswith("device")]

for attempt in range(6):
    live = [d for d in adb_devices() if d.startswith(TARGET + ":")]
    if live:
        print("DEVICE:", live[0])
        sys.exit(0)
    ports = scan()
    print(f"attempt {attempt}: OPEN {ports}")
    for p in ports:
        r = subprocess.run(["adb", "connect", f"{TARGET}:{p}"],
                           capture_output=True, text=True, timeout=15)
        print("  connect", p, ":", (r.stdout + r.stderr).strip())
    time.sleep(3)

live = [d for d in adb_devices() if d.startswith(TARGET + ":")]
if live:
    print("DEVICE:", live[0])
    sys.exit(0)
print("NOT-CONNECTED — if scans stay empty: wireless debugging needs first unlock after "
      "reboot; if connect shows unauthorized/closed: request fresh pairing code")
sys.exit(1)
