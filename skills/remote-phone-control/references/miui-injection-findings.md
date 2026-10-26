# MIUI Injection & Wake — Evidence Log (2026-10-24, Redmi 9 / Android 12 / MIUI 13)

Condensed test matrix from the investigation session. Commands are reproducible probes;
timestamps are session-relative facts, not guarantees about future state.

## Injection (`input`) test results

| When / state | Result |
|---|---|
| Before user enabled "USB debugging (Security settings)" | `keyevent` → SecurityException (INJECT_EVENTS) |
| After toggle ON (first time) | `keyevent 223` SLEPT the screen ✅; volume keepalive held screen ✅ |
| Same era, motion tests with pointer_location+show_touches ON | drag → **0.00% pixel change**, overlay never drew → touches had NO effect despite no exception |
| Mid-day flaps | swipe accepted → SecurityException → accepted, within minutes (both key & motion classes) |
| After `adb reboot` (reboot of phone) | first probe `input swipe` ACCEPTED ✅; `keyevent223` relock sent ✅ — injection re-armed by reboot |
| ~2-5s after a wake event | frequently SecurityException (transient block window), passes after settling |
| `pm grant com.android.shell android.permission.INJECT_EVENTS` | SecurityException: shell lacks GRANT_RUNTIME_PERMISSIONS |
| `cmd appops set com.android.shell INJECT_EVENTS allow` | `Unknown operation string` (no such appop) |
| `dumpsys package com.android.shell \| grep INJECT_EVENTS` | **granted=true even while probes throw** → MIUI runtime layer above PM |
| Wake-type keys (224 WAKEUP, 26 POWER, 82 MENU, 126 MEDIA) | no exception sometimes, but **never woke the screen** |
| Pixel-diff end-to-end (Settings scroll, calculator tap) | 0.00% — no observable effect ever, across lock states |

**Conclusion**: never build flows on `input`. Probe with
`input swipe50018005001200150` only to learn the current window; use AutoJS6 for gestures.

## Settings / permissions on this MIUI

- `settings put system ...` → SecurityException UNTIL
  `appops set com.android.shell WRITE_SETTINGS allow` (then works — used for
  `pointer_location`, `show_touches`).
- `settings put secure ...` → SecurityException, not grantable from shell
  (`enabled_accessibility_services` readable but not writable).
- `settings list global` shows `adb_enabled`, `adb_wifi_enabled` — NOT the MIUI security
  toggle (it is not a settings key; no key found in global/secure/system namespaces).
- Candidate MIUI appops seen: `MIUIOP(10008)`, `MIUIOP(10033)` (settable numerically,
  setting them did NOT unlock injection).

## Wake method matrix (display control)

| Method | Effect |
|---|---|
| AutoJS6 `device.wakeUp()` | ✅ (script ran with screen off → woke) |
| `cmd notification post -S bigtext -t X y z` | ✅ most reliable binder path; flapped once for ~15 min; screen can re-sleep ~2-5s later |
| `am start -n com.miui.calculator/.cal.CalculatorActivity` | ✅ once (with focus moving), ❌ other times |
| `input keyevent 223` (SLEEP) | ✅ when injection window open |
| `input keyevent 224/26/82/126` | ❌ never wake |
| `svc power` / `cmd power` | no wake subcommand available |

State quirks: `mWakefulness=Awake` + `mScreenState=OFF` desync observed repeatedly.
`screen_off_timeout = 2147483647` (MAX). Proximity sensor read FAR (5.00) — not the culprit.

## Capture (screencap) semantics

- Lit real frame: **>100KB** (lockscreen ≈3.34MB, calculator ≈84KB, settings ≈135KB)
- Off/black frame: **15197 bytes** exactly (constant across days)
- **0 bytes**: (a) capture during transition — retry; (b) hang killed at timeout — retry;
  (c) suspected secure-screen block while bouncer up (never disproved: bouncer never
  captured; `screenrecord --time-limit3` also produced 0B in that era)
- `exec-out screencap -p` (single roundtrip) beats `shell screencap + pull`.
- `uiautomator dump` on lockscreen: stale/minimal trees; bouncer nodes excluded.

## Bouncer (pattern screen) raising — attempts that did NOT show a bouncer

Shell: fast flick120ms, slow drag1000ms from y1900/2150/2320/1700, keyevent82,
`cmd statusbar collapse`, `wm dismiss-keyguard`, `android.app.action.CONFIRM_DEVICE_CREDENTIAL`,
`com.android.settings/.ConfirmLockPassword|ConfirmLockPattern`, settings intents.
AutoJS6 accessibility `gesture(1400ms, ...)` long drags ×4 (while locked) executed ok but
PatternView never found — BUT keyguard nodes are invisible to a11y (`classNameMatches(".*").find()`
= 0 nodes), so "bouncer up but invisible" was never ruled out; screenrecord/screencap gave
no positive frame either.

## Pairing / ports timeline (for rotation expectations)

Pairs: `guid=adb-570c68110404-7WtBWY` survived reboot + wireless-debug off/on.
Main-port sequence seen: 43775 → 41267 → 45591 → 44581 → 34981 → 35669.
Wireless debug does not listen at all until first unlock after reboot (empty scans,
tunnel healthy).

## Tailscale note (dead end, don't retry)

Hosted Tailscale signup requires an IdP (Google/Microsoft/GitHub/Apple) — no Houston creds
exist for any (Google OAuth also bot-blocked; credential-manager skill documents that).
The VPS has tailscale package installed but logged out; the working network is
self-hosted WireGuard. Don't propose Tailscale again without new credentials.
