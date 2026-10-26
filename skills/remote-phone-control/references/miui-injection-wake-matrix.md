# MIUI Injection / Wake Test Matrix (Redmi 9, Android 12, MIUI 13)

Session 2026-10-24 — every row verified by live test on this device. States
FLAP over time; re-probe before relying on a row.

## Injection (INJECT_EVENTS)

Blocking error (verbatim):
```
java.lang.SecurityException: Injecting to another application requires
INJECT_EVENTS permission
  at com.android.server.input.InputManagerService.injectInputEventInternal(InputManagerService.java:912)
```
Thrown by: `input swipe`, `input tap`, `input motionevent`, `input keyevent`,
`monkey` ("System appears to have crashed at event 1 of N ...").

Key contradiction (MIUI-specific):
```
dumpsys package com.android.shell | grep INJECT_EVENTS
  android.permission.INJECT_EVENTS: granted=true     ← PM says granted
input swipe ... → SecurityException                   ← runtime still blocks
```
⇒ MIUI layers its own runtime gate tied to dev toggle
**USB debugging (Security settings)** (MIUI shows the literal Thai translation of this label).

Observed lifecycle:
- Toggle ON (user, ~03:00) → keyevents worked for hours (223 slept screen,
  volume keepalive held screen). Motion: no-exception but 0.00% pixel effect
  in the one clean pointer-overlay test (overlay itself: `settings put system
  pointer_location 1` + `show_touches 1` after appops grant).
- Later: everything SecurityException again (revert with no visible cause).
- User toggled lock/security settings in between — possible interaction unknown.
- Toggle off→on + wireless-debug off→on re-init: did NOT re-arm (4×15s probes
  over 4 min: all blocked).
- `cmd appops set com.android.shell 10033 allow` / `10008 allow` accepted
  (MIUIOP custom ops exist: MIUIOP(10008) allow since ~18h, MIUIOP(10033)
  allow time updated during session) → swipe STILL blocked ⇒ not the gate,
  or gate reads elsewhere.
- `pm grant com.android.shell android.permission.INJECT_EVENTS` →
  `SecurityException: Neither user 2000 ... has GRANT_RUNTIME_PERMISSIONS`.
- Final recommendation outstanding: **reboot phone** (after Always-on VPN).

`cmd appops get com.android.shell` (interesting lines):
```
WRITE_SETTINGS: allow; ...            ← after our own grant, enables settings put system
MIUIOP(10008): allow
MIUIOP(10033): allow
```

## Touch injection — verification methodology

- Never trust exit code / absence of exception. Effect check:
  ```python
  # open scrollable UI first: am start -a android.settings.SETTINGS
  diff = mean(abs(A-B) > 12) on greyscale captures   # >2% works, ~0.16% = clock tick only
  ```
- Pointer-location overlay (`settings put system pointer_location 1`,
  `show_touches 1`; needs `cmd appops set com.android.shell WRITE_SETTINGS
  allow` first) renders injected touch paths IF they reach the pipeline —
  our injected drag produced 0.00% change with overlays ON ⇒ events never
  dispatched. Turn overlays off afterwards (put ... 0).
- False-negative trap: horizontal swipe on calculator = no visual change even
  if touch works. Use a LIST.

## sendevent (raw /dev/input)

- Nodes: `crw-rw---- root input`; shell groups include `1004(input)` ⇒ DAC ok.
- Touchscreen = `/dev/input/event1` (props: ABS_MT_POSITION_X 0-1080,
  Y 0-2340 — 1:1, INPUT_PROP_DIRECT).
- `sendevent /dev/input/event1 0 0 0` → `Permission denied` ⇒ SELinux denies
  shell chr_file write despite unix perms. Dead end without root.

## Wake matrix (all methods tried; flaps)

| Method | Verdict |
|---|---|
| `input keyevent 223` (SLEEP) | works while grant open |
| `input keyevent 224` / `26` (WAKEUP/POWER) | no exception, screen NEVER wakes (MIUI) |
| `input keyevent 82` / `126` | blocked or no-wake |
| `cmd notification post -S bigtext -t "Houston" "tag" "text"` | primary wake ✅ for hours → later stopped (posting succeeds, state stays Asleep) |
| `am start -n com.miui.calculator/.cal.CalculatorActivity` | 1 success / 4 failures — opportunistic |
| volume `keyevent 24/25` as keepalive (resets sleep timer) | works while grant open |
| physical power button | always |

Diagnostics when wake fails:
- proximity: `dumpsys sensorservice | grep -A10 "PROXIMITY:"` → value `5.00` = FAR (not covered).
- battery: `dumpsys battery` → level/status/voltage (80%, charging, 4134mV healthy).
- timeout: `settings get system screen_off_timeout` = `2147483647` (MAX ⇒ screen never self-sleeps; only power/sleep keys sleep it).

## Wake/lock-state reads

- `dumpsys power | grep mWakefulness=` → Awake/Asleep
- `dumpsys display | grep mScreenState=` → ON/OFF (can desync briefly)
- `dumpsys window | grep mCurrentFocus` → keyguard iff NotificationShade/systemui
- `dumpsys lock_settings | grep CredentialType` → Pattern/None (needs no cred to read)

## Settings/appops notes

- `settings put global ...` → SecurityException (e.g. adb_enabled) even when
  `settings put system ...` works after WRITE_SETTINGS appop grant.
- No settings key exists for the MIUI security-debug toggle (grepped
  global/secure/system for adb|debug|inject|simul|usb|secur|mock).
  Visible nearby: `adb_enabled=1`, `adb_wifi_enabled=1`, `miui_keyguard=2`.
- `getprop`: `ro.adb.secure=1`, `persist.sys.usb.config=adb`.
