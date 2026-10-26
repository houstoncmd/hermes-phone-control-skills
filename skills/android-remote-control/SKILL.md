---
name: android-remote-control
description: "Control an Android phone remotely from a Houston server — ADB over Tailscale (wireless-debugging pair/connect, screencap, input injection, scrcpy) with a no-root Termux reverse-tunnel fallback. Use when the user asks to view, control, or automate their own phone from a distance (\"control my phone remotely\", remote-control my phone, screenshot the phone screen)."
version: 0.1.0
author: Houston
license: MIT
metadata:
  hermes:
    tags: [android, adb, tailscale, remote-control, scrcpy, mobile, teleop, wireless-debugging]
    related_skills: [remote-server-management, reverse-engineer-anything]
---

# Android Remote Control (ADB over Tailscale)

Houston can see and control the user's Android phone from the Hermes VPS:
phone runs **Tailscale** + Android's built-in **Wireless debugging** → VPS does
`adb pair` / `adb connect` to the phone's tailnet IP → then screenshot (→ vision,
sent as MEDIA:) and inject taps/swipes/text. No port is ever exposed to the
public internet — traffic is end-to-end encrypted inside the tailnet and visible
only to devices in the user's Tailscale account.

## When to Use
- "control my own phone remotely" / remote-control my phone / screenshot the phone screen / drive the phone for me
- Automating or inspecting UI on the user's own device (combine with REA tools
  `mcp_rea_capture_adb_screen` etc. when the goal is app analysis).

Counter-triggers (route elsewhere):
- Phone lost/stolen → Samsung SmartThings Find (locate/ring/lock/wipe only — NOT full control).
- User wants to drive it themselves from a PC → recommend AnyDesk/TeamViewer (5-minute setup).
- iPhone → this skill does not apply.

## Status on hermes VPS (2026-10-24)
- Installed & running: `adb` 34.0.4, `scrcpy` 1.25, `tailscale` 1.104.2
  (`tailscaled` enabled; node hostname `hermes`, `--accept-dns=false`).
- LIVE device: **MicrowareMobile** (Redmi 9) over WireGuard `10.66.66.2` — see
  `references/microware-mobile.md` for endpoint, device card, and MIUI-specific blocks.
  Second peer **DuckZilla** (Moto G9 Plus, stock Android — no MIUI blocks) = `10.66.66.3`,
  added 2026-10-25 via the add-a-peer recipe in `devops/remote-phone-control` §Adding another phone.
  Tailscale path not yet in use; both transports are valid, WireGuard is the one proven working.
- Re-verify before use: `adb devices`.

## VPS Side Setup (idempotent — already done on hermes; redo on a new host)
Local sudo: plain `sudo ...` works (terminal tool auto-injects) — but NOT inside
`| sudo tee` or `curl|sh`; see remote-server-management →
`references/local-server-administration.md` §Sudo Execution Pattern.

```bash
# adb + scrcpy
sudo apt-get update -qq && sudo apt-get install -y -qq adb scrcpy

# tailscale repo — write the file as the user, then sudo install (never | sudo tee)
printf 'deb [signed-by=/usr/share/keyrings/tailscale-stable.gpg] https://pkgs.tailscale.com/stable/ubuntu noble main\n' > /tmp/ts.list
sudo install -m 0644 /tmp/ts.list /etc/apt/sources.list.d/tailscale.list
curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/noble.noarmor.gpg -o /tmp/ts.gpg
sudo install -m 0644 /tmp/ts.gpg /usr/share/keyrings/tailscale-stable.gpg
sudo apt-get update -qq && sudo apt-get install -y -qq tailscale
sudo systemctl enable --now tailscaled

# join tailnet (accept-dns=false keeps the VPS resolver untouched)
sudo tailscale up --accept-dns=false --hostname=hermes
```

## Phone Side (user runs — send these steps)
1. Open the auth URL from `tailscale status` → login (Google/GitHub/Microsoft).
2. Install **Tailscale** app (Play/Galaxy Store) → login SAME account → toggle ON.
3. Enable wireless debugging (once): Settings → About phone → Software info →
   tap **Build number 7×** → back → Developer options → ON → **Wireless debugging** → ON.
4. Ask the user to send: main screen **IP address & port** AND (from
   **"Pair device with pairing code"**) the **IP, port, 6-digit code** — keep that
   dialog open until pairing completes.

## Pair & Connect (ports CHANGE every toggle/reboot/phone restart)
```bash
adb pair <phone-tailnet-ip>:<pair-port> <6-digit-code>
adb connect  <phone-tailnet-ip>:<connect-port>   # DIFFERENT port from pairing
adb devices                                       # expect: <ip>:<port> device
```
The IP shown on the phone screen is the LAN IP (192.168.x.x) — adbd listens on
all interfaces, so connect using the phone's **Tailscale 100.x.y.z** IP
(seen in `tailscale status` peer list). Keep re-pairing steps handy: each new
wireless-debugging session needs a fresh pairing code.

## Control Commands
```bash
adb exec-out screencap -p > /tmp/phone.png      # screenshot → send as MEDIA:
adb shell dumpsys window | grep -m1 mCurrentFocus   # which app is foreground
adb shell input tap X Y
adb shell input swipe X1 Y1 X2 Y2 [ms]
adb shell input keyevent 26                     # screen off/on (wake test)
adb shell input text 'ASCII-only'
adb shell am start -n <pkg>/<activity>
adb shell monkey -p <pkg> -c android.intent.category.LAUNCHER 1
scrcpy --record=/tmp/clip.mp4 --no-display      # headless VPS: record, don't mirror
```

## Fallback: Termux reverse tunnel (no root needed on VPS)
Use when the Tailscale app is unavailable or adbd won't answer on the tailnet IP.
Phone initiates everything (phone → VPS:22 outbound, allowed by carriers):
1. VPS: create a dedicated keypair, append pubkey to `~/.ssh/authorized_keys` (no root).
2. Phone (Termux): `pkg install openssh android-tools` → pair wireless debugging
   locally (`adb pair <own-lan-ip>:<port> <code>`) → `adb tcpip 5555`.
3. Termux runs a persistent loop: `ssh -N -R 15555:127.0.0.1:5555 user@YOUR_VPS_PUBLIC_IP`.
4. VPS: `adb connect 127.0.0.1:15555` → same control commands as above.

## MIUI (Redmi 9 / lancelot) Specifics — see `references/microware-mobile.md`
MIUI adds restrictions that stock-AOSP advice doesn't cover:
1. **`settings put global device_name <name>` → `SecurityException: WRITE_SECURE_SETTINGS`** even from adb shell (MIUI protects device-name writes). `setprop net.hostname` / `setprop persist.sys.*` also fail (SELinux). Renaming the device MUST go through UI: Settings → About phone → Device name, driven by taps after unlock.
2. **Locked screen ⇒ input injection is blocked.** `input keyevent KEYCODE_WAKEUP`/`26` throws `SecurityException: Injecting to another application requires INJECT_EVENTS` and `wm dismiss-keyguard` does nothing (secure pattern lock). `cmd power wake` = "Unknown command" on this MIUI. Wake path that works: `svc power stayon true` (sometimes wakes + keeps on while USB-powered). ~~ADB cannot bypass a pattern lock, so plan on asking the user to unlock for any UI task.~~ **SUPERSEDED 2026-10-24/25**: the proven remote unlock is NOT `input`/adb — it's the AutoJS6 accessibility path in `devops/remote-phone-control` (calibrated pattern stroke, `scripts/unlock_phone.sh`, 7/7 verified). Load that skill before telling the user they must unlock by hand.
3. **Screen-off ⇒ `screencap` returns a valid-looking 1080×2340 PNG that is 100% black** — not an error, exit 0. Detect it fast: `sha256sum` two captures; identical hashes = nothing rendered. `uiautomator dump` on a black screen yields only `systemui:id/scrim_*` nodes. Always confirm `dumpsys power | grep mWakefulness=` + `dumpsys display | grep mState=` before trusting a screenshot.
4. While keyguard is up, `dumpsys window | grep mCurrentFocus` shows `NotificationShade` regardless of which activity you `am start`ed — the launch may have succeeded underneath (check `mFocusedApp`).

## MIUI (Xiaomi/Redmi) — Extra Restrictions & Workarounds
MIUI layers additional security on top of stock Android. When the target is a
Redmi/Xiaomi device, read `references/miui-adb-restrictions.md` FIRST — it has
the full command recipes. Headlines:
- **`input` injection (tap/swipe/keyevent) is BLOCKED while the screen is
  locked** → `SecurityException: Injecting to another application requires
  INJECT_EVENTS permission`. Fix requires one-time user action: enable
  **Settings → Additional settings → Developer options → "USB debugging
  (Security settings)"**. Without it you can never draw an unlock pattern remotely.
- **`settings put global/secure ...` is BLOCKED** (WRITE_SECURE_SETTINGS
  SecurityException) — notably `device_name` cannot be changed via ADB at all.
  `settings put system ...` (e.g. `screen_off_timeout`) still works.
- **Waking the screen: `input keyevent 26/224` is unreliable** over wireless
  ADB and often throws the same INJECT_EVENTS error. The reliable waker is
  `adb shell svc power stayon true` → poll `dumpsys display | grep mState=`
  (expect `mState=ON`).
- **`screencap` lies when the display is off**: it returns a constant ~15 KB
  all-black PNG (or 0 bytes / RC=1 in deeper sleep). ALWAYS check
  `dumpsys display | grep mState=ON` before trusting a capture. A real
  1080x2340 UI screenshot is ~3.7 MB.
- **MIUI proximity "screen-on" guard** (`enable_screen_on_proximity_sensor=1`
  in global settings) can blank the screen seconds after waking and shows a
  `ScreenOnProximitySensorGuide` window. Not writable via ADB (global writes
  blocked) — keep re-waking with `svc power stayon true` and act fast.

### `locksettings` — rootless credential control (works on MIUI)
`adb shell locksettings` needs NO root and accepts the stored pattern:
```bash
P=$(tr -d '-' < /tmp/.lk)                 # vault pattern is keypad 1-9 dash order
adb shell locksettings verify --old "$P"  # "Lock credential verified successfully"
adb shell locksettings set-pattern "$P"   # restore after a test
adb shell locksettings clear --old "$P"   # remove credential (RESTORE AFTERWARD)
adb shell locksettings set-disabled --old "$P" true   # disable keyguard
```
⚠️ If you clear/disable the lockscreen for a test, ALWAYS restore
(`set-pattern` + `verify` + `get-disabled` → false) before reporting done.
Vault entry for this device: site_name "Phone Lock (Redmi 9 / Houston remote)",
pattern stored as keypad 1-9 in dash order — strip dashes before use, and never
echo the pattern in chat.

## Pitfalls
1. **Tailscale's stock `noble.list` has NO `signed-by=`** → apt GPG error
   `NO_PUBKEY 458CA832957F5868` / "repository is not signed". Write the list
   line manually with `[signed-by=/usr/share/keyrings/tailscale-stable.gpg]` (see setup above).
2. **`tailscale up`/`tailscale login` block until the user authenticates** and will
   hit the tool timeout ("context canceled"). The auth URL survives — read it from
   `tailscale status` ("Log in at: ..."). For background login:
   `sudo sh -c 'nohup tailscale login >/tmp/ts_login.txt 2>&1 &'` — note `disown`
   does not exist in `sh` (dash); use bash or omit it.
3. **`printf ... | sudo tee` breaks the sudo auto-rewrite** — sudo reads the piped
   data as the password. Write as user, then `sudo install src dst`.
4. **mDNS discovery does not cross the tailnet** — `adb mdns services` will NOT
   find the phone; always `adb connect <tailnet-ip>:<port>` explicitly.
5. **Pairing port ≠ connect port** — both must be read from the phone; pairing
   dialog and main wireless-debugging screen show different ports.
6. **Headless VPS has no display** — scrcpy can't open a window; use
   `adb exec-out screencap` (send PNG as MEDIA:) or `scrcpy --record --no-display`.
7. **`input text` is ASCII-only** — Thai text needs ADBKeyboard or a clipboard
   workaround; don't promise Thai typing via plain `input text`.
8. **Never expose adb publicly** — tailnet/loopback only; no port-forwards on the router.

## Verification Checklist
- [ ] `tailscale status` lists the phone as a peer (100.x.y.z).
- [ ] `adb devices` shows `<ip>:<port> device` (not `offline`/`unauthorized`).
- [ ] `adb exec-out screencap -p` returns a real PNG → send to user as proof.
- [ ] User confirms a `input keyevent 26` (screen toggle) was visible on the phone.
