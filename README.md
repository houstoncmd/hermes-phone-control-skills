# 📱 Android Remote-Control Skills (Hermes Agent)

A pair of skills for **viewing, driving and unlocking an Android phone remotely** from a Linux
server (VPS) running Hermes Agent (by Nous Research) — proven live on MIUI (Redmi 9) and stock
Android (Moto G9 Plus).

> ⚠️ **This repository is PUBLIC** — every file has been reviewed and stripped of secrets:
> **no passwords, no unlock pattern, no private keys, no real server IP, no personal email.**
> See [Redacted](#-redacted) for the full list.

---

## 📦 What's in this repo

| Folder | What it is | When to use it |
|---|---|---|
| [`skills/remote-phone-control`](skills/remote-phone-control/) | Main skill — **WireGuard tunnel + adb + AutoJS6**: unlock, screen reading, tap/swipe, notifications, watchdog | Real control on MIUI devices (where adb `input` is blocked) |
| [`skills/android-remote-control`](skills/android-remote-control/) | Secondary skill — **ADB over Tailscale** + no-root Termux tunnel fallback + an MIUI restriction primer | Starting from scratch, stock Android, or no WireGuard |

Skill layout follows the Hermes Agent format (Hermes loads `SKILL.md` + `references/` + `scripts/` + `templates/` automatically).

```
skills/
├── remote-phone-control/
│   ├── SKILL.md                 ← main guide (live state, procedures, pitfalls)
│   ├── references/*.md          ← MIUI injection matrix, app-content reading, settings map, hardware probes
│   ├── scripts/*.sh, *.py       ← unlock/lock, port scan, fire_js, notifications, watchdog
│   └── templates/unlock_script.js
└── android-remote-control/
    ├── SKILL.md
    └── references/*.md          ← MIUI ADB restrictions, device card
```

---

## 🏗️ Architecture

```
┌────────────────────┐        WireGuard (split tunnel)        ┌─────────────────────────┐
│  Android phone     │  10.66.66.0/24, UDP 51820             │  Linux VPS (Hermes)     │
│  • WireGuard app   │ ◄───────────────────────────────────► │  • wg0 10.66.66.1/24    │
│  • Wireless debug  │   adb pair / adb connect (TCP)        │  • adb, python3         │
│  • AutoJS6         │                                       │  • Hermes Agent (AI)    │
└────────────────────┘                                       └─────────────────────────┘
```

* **WireGuard tunnel** = the only way the server reaches the phone (no port is ever exposed to the public internet).
* **adb over wireless debugging** — the port **randomises on every** toggle/reboot, so it always has to be re-scanned.
* **AutoJS6 (accessibility service)** = the actual hands for tap / drag / unlock
  (on MIUI adb's `input tap/swipe` is blocked by `INJECT_EVENTS` — never build on it).

---

## 🚀 Getting started

### 1) Server side (VPS)

```bash
sudo apt-get update && sudo apt-get install -y adb wireguard qrencode python3

# Generate the server key pair (never share the private key)
wg genkey | tee /etc/wireguard/server.key | wg pubkey > /etc/wireguard/server.pub

# /etc/wireguard/wg0.conf  (replace YOUR_VPS_PUBLIC_IP with your real server IP)
#   [Interface]
#   PrivateKey = <server private key>
#   Address    = 10.66.66.1/24
#   ListenPort = 51820
#   PostUp   = iptables -A FORWARD -i wg0 -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
#   PostDown = iptables -D FORWARD -i wg0 -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE

sudo systemctl enable --now wg-quick@wg0
sudo ufw allow 51820/udp          # + 22/tcp per your own policy
```

> Ready-made script: [`skills/remote-phone-control/scripts/wg_setup.sh`](skills/remote-phone-control/scripts/wg_setup.sh)

### 2) Add the phone as a peer

```bash
wg genkey > /tmp/phone.priv; wg pubkey < /tmp/phone.priv > /tmp/phone.pub; wg genpsk > /tmp/phone.psk

# Append the [Peer] block to wg0.conf, then apply live (no restart, other peers stay up)
sudo wg set wg0 peer "$(cat /tmp/phone.pub)" preshared-key /tmp/phone.psk allowed-ips 10.66.66.2/32
```

Create the client config for the phone (⚠️ **send it by email / a private channel only — never post it in chat**):

```ini
[Interface]
PrivateKey = <phone private key>
Address    = 10.66.66.2/32
DNS        = 1.1.1.1, 8.8.8.8

[Peer]
PublicKey  = <server public key>
PresharedKey = <psk>
AllowedIPs = 10.66.66.0/24          # SPLIT TUNNEL: general traffic exits via the phone (default)
Endpoint   = YOUR_VPS_PUBLIC_IP:51820
PersistentKeepalive = 25
```

```bash
qrencode -t ansiutf8 < wg-phone.conf   # let the phone scan it, or send the .conf file
```

### 3) Phone side (one-time, done by the user)

1. Install the **WireGuard** app → import (scan the QR) → toggle it ON.
2. Settings → Battery → WireGuard → **No restrictions**.
3. Settings → Connection & sharing → VPN → ⚙️ next to WireGuard → enable **Always-on VPN**.
4. Enable **Developer options** (Settings → About phone → Software info → tap "Build number" 7 times)
   → turn ON **Wireless debugging**.
5. Install **AutoJS6** (F-Droid/GitHub) → Settings → Additional settings → Accessibility →
   Installed services → switch **AutoJS6** ON.

### 4) Connect adb (has to be repeated whenever the port rotates)

```bash
ping -c2 10.66.66.2                                    # the tunnel must be up first
python3 scripts/scan_connect.py 10.66.66.2             # sweeps every port + adb connect for you
adb devices                                             # expect <ip>:<port> device
```

First-time pairing (the **6-digit code** must be sent from the phone within ~2 minutes):

```bash
adb pair 10.66.66.2:<pair-port> <6-digit-code>
```

> 📌 Android rule: **after a reboot wireless debugging stays off until the screen is unlocked once**
> → an empty scan while ping works = ask for that unlock / switch flip, not a re-pair.

---

## 🎮 Everyday commands

| Task | Command |
|---|---|
| Unlock the screen (automatic) | `scripts/unlock_phone.sh` (exit 0 = success) — re-test with `--force` |
| Lock the screen | `scripts/lock_phone.sh` |
| Scan ports + attach adb | `scripts/scan_connect.py <tunnel-ip>` |
| Fire an AutoJS6 script + read its output | `scripts/fire_js.sh myscript.js` (results come back on logcat tag `GlobalConsole`) |
| Mute / unmute app notifications | `scripts/app_notifications.py off\|on\|status [--apps shopee,tiktok]` |
| Turn a dump XML into readable rows | `scripts/show_rows.py u.xml` |
| Tunnel watchdog for both phones (silent when healthy) | `scripts/mw_watchdog.py` (run by a cron in `no_agent=True` mode) |
| Screenshot → send for review | `adb exec-out screencap -p > shot.png`, then send the file (size check: `>100KB` = a real frame) |
| Which app is in the foreground | `adb shell dumpsys window \| grep mCurrentFocus` |

The correct order of operations (critical — doing it wrong destroys the evidence):

```
unlock → open app → harvest → report → close apps → home → lock
```

---

## 🔐 Adapt it to your own phone (you supply the secrets)

This repo ships no real values — you add them on your own machine only:

1. **Unlock pattern**
   * Keep it in the Hermes vault (e.g. `~/.hermes/data/vault.json`, entry `Phone Lock ...`)
     or in a `0600` file — **never in git, chat, or a screenshot**.
   * Put it in [`templates/unlock_script.js`](skills/remote-phone-control/templates/unlock_script.js)
     at `SEQ = "YOUR_PATTERN"` (7 digits in the order your stroke touches them;
     keypad layout: 1 = top-left … 9 = bottom-right).
   * **First real calibration**: turn on pointer-location
     (`settings put system pointer_location 1`), have the user draw the pattern once, pull the
     frame and locate the 9 dot centres (full algorithm in
     [`references/grid-detect-and-draw.md`](skills/remote-phone-control/references/grid-detect-and-draw.md)).
   * ⛔ **Never guess coordinates** — 5 wrong attempts = 30-second lockout.
2. **Server IP** — replace `YOUR_VPS_PUBLIC_IP` everywhere.
3. **WireGuard keys / PSK** — generate them on your own box; never commit them.
4. **Delivery email** — replace `you@example.com`.

> The `locksettings` command (in `android-remote-control`) can read/set a pattern over adb without
> root — read it from the vault into a `0600` temp file only, and **never echo the value to stdout/chat**.

---

## ⚠️ Redacted

| Item | Replaced with | Why |
|---|---|---|
| Real unlock pattern (shape + keypad digits + stroke coordinates) | `YOUR_PATTERN` | The main secret — it opens the device |
| Server public IP | `YOUR_VPS_PUBLIC_IP` | Avoids publishing an attack target |
| Personal email | `you@example.com` | Personally identifiable information |
| Home paths `/home/<user>` | `~` / `$HOME` | Portability + no username disclosure |
| WireGuard private key / PSK | not in the repo (generate new) | Credential |

Re-run this check over the whole repo before every push:
pattern digits, `-----BEGIN`, real server IP, `@gmail`, `password=`, tokens.

---

## 🧩 Install as Hermes skills

```bash
git clone https://github.com/<owner>/<repo>.git
cp -r <repo>/skills/remote-phone-control   ~/.hermes/skills/devops/     # or straight into ~/.hermes/skills/
cp -r <repo>/skills/android-remote-control ~/.hermes/skills/
```

Hermes reads `SKILL.md` (name/description/tags) and fires the skill automatically when the user
asks about their phone ("unlock the phone", "look at my screen", "mute shopee notifications").

---

## 🔥 Common pitfalls (summary)

1. adb ports **rotate on every** wireless-debug re-init / reboot → always rescan, never reuse a port.
2. Pairing codes expire in ~2 min (`Wrong password or connection was dropped` = stale, ask again).
3. Screen off ≠ device asleep — always check `dumpsys display | grep mScreenState`
   (not just `mWakefulness`).
4. With the screen off, `screencap` returns a solid black PNG of a constant size (~15 KB) or 0 bytes —
   a real frame is `>100KB`.
5. Never build flows on `input tap/swipe` on MIUI (it flaps) → use **AutoJS6 `gesture()`**.
6. `logcat -c` before firing a script every time, and only parse `GlobalConsole` + the `HOUSTON` marker.
7. On MIUI the keyguard is **not in the accessibility tree** → you cannot read dot bounds, you must
   replay the calibrated stroke.
8. MIUI kills WireGuard when the screen goes off (PowerKeeper `AutoLockOffClean`) → set
   "No restrictions" + turn off "Clear cache when device is locked" + Always-on VPN —
   **Background process limit does not help**.
9. Recents on MIUI: fling cards one by one horizontally — "Clear all" takes WireGuard down with it.
10. Host `uiautomator dump` and AutoJS6 fight over the same accessibility service → use one reader
    per phase.

> The full, evidence-backed list lives in `SKILL.md` → **Pitfalls**.

---

## 📄 License

MIT — see [LICENSE](LICENSE)

**Warning**: only use this on devices **you own or have explicit permission to control**.
Unlocking or driving somebody else's device without authorization is illegal.
