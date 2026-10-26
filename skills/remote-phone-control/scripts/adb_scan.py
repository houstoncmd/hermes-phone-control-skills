#!/usr/bin/env python3
"""Discover + optionally pair/connect the Android phone over the WireGuard tunnel.

Ports rotate every session (pairing port per dialog open, main port per
wireless-debug re-init) — always re-scan, never hardcode.

Usage:
  python3 adb_scan.py --ip 10.66.66.2                   # list open ports
  python3 adb_scan.py --ip 10.66.66.2 --pair 123456     # try pairing on each open port
  python3 adb_scan.py --ip 10.66.66.2 --pair 123456 --connect
"""
import argparse
import socket
import subprocess
import time
import concurrent.futures


def scan(ip):
    open_ports = []

    def probe(p):
        s = socket.socket()
        s.settimeout(1.0)
        try:
            return p if s.connect_ex((ip, p)) == 0 else None
        finally:
            s.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=800) as ex:
        for r in ex.map(probe, range(1024, 65536), chunksize=64):
            if r:
                open_ports.append(r)
    return sorted(open_ports)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ip', default='10.66.66.2')
    ap.add_argument('--pair', metavar='CODE', help='6-digit pairing code; tries every open port')
    ap.add_argument('--connect', action='store_true',
                    help='adb connect to every open port except the paired one')
    args = ap.parse_args()

    ports = scan(args.ip)
    print('OPEN:', ports)

    paired_port = None
    if args.pair:
        for p in ports:
            r = subprocess.run(['adb', 'pair', f'{args.ip}:{p}', args.pair],
                               capture_output=True, text=True, timeout=20)
            out = (r.stdout + r.stderr).strip()
            print(f'pair {p}: {out}')
            if 'Successfully paired' in out:
                paired_port = p
                break
        if not paired_port:
            print('PAIR_FAILED — code expired/rotated; ask the user for a fresh one')
            return

    if args.connect:
        for p in ports:
            if p == paired_port:
                continue
            r = subprocess.run(['adb', 'connect', f'{args.ip}:{p}'],
                               capture_output=True, text=True, timeout=15)
            print(f'connect {p}: {(r.stdout + r.stderr).strip()}')
        time.sleep(2)

    print(subprocess.run(['adb', 'devices', '-l'], capture_output=True, text=True).stdout)


if __name__ == '__main__':
    main()
