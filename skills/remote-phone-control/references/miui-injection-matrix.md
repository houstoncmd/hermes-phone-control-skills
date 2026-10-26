# MIUI Injection / Wake / Capture — Evidence Matrix (2026-10-24 session)

Device: Redmi 9 (M2004J19C / lancelot), Android 12, MIUI. adb over wireless debugging via
WireGuard tunnel. Each row = observed live, with the exact error/size that identifies it.

## Injection (InputManagerService)

| Command | Gate state A (toggle OFF) | Gate state B (toggle ON) |
|---|---|---|
| `input keyevent 223` (SLEEP) | SecurityException INJECT_EVENTS | ✅ sleeps screen |
| `input keyevent 26/224/82/126` (POWER/WAKEUP/MENU/MEDIA) | SecurityException | ⚠️ no exception BUT screen never wakes |
| `input keyevent 24/25` (volume) | SecurityException | ✅ no exception, user-activity (keepalive works) |
| `input tap/swipe/text/motionevent` | SecurityException ("Exception occurred while executing 'swipe'") | no exception, but **no visible effect** in a 0.16% pixel-diff test (touch may still be dead — verify with diff, never trust exit code) |
| `monkey -p pkg --pct-touch ...` | crashes: "System appears to have crashed at event 1" + INJECT_EVENTS stack | untested under B |
| `sendevent /dev/input/eventN` | — | `Permission denied` (unix group OK: shell ∈ group input, node crw-rw---- root:input; SELinux denies — dead end) |
| `wm dismiss-keyguard` | binder OK; unlocks only non-secure locks | same |
| `pm grant com.android.shell android.permission.INJECT_EVENTS` | SecurityException (no GRANT_RUNTIME_PERMISSIONS) | — |
| `cmd appops set com.android.shell INJECT_EVENTS allow` | `Error: Unknown operation string: INJECT_EVENTS` | — |

Gate state flips: enabling "USB debugging (Security settings)" grants it; entering MIUI
settings/lock flows later reset it WITHOUT notice. **Pre-check every session.**

Custom appops seen on shell uid: `MIUIOP(10008): allow`, `MIUIOP(10033): allow`,
`WRITE_SETTINGS` (default deny until granted).

## Settings writes

| Attempt | Result |
|---|---|
| `settings put system pointer_location/show_touches` | SecurityException WRITE_SETTINGS (MIUI) |
| `cmd appops set com.android.shell WRITE_SETTINGS allow` then retry | ✅ works — enables pointer-location/show-taps diagnostics |
| `settings put global adb_enabled 1` | SecurityException even after WRITE_SETTINGS grant (protected) |

## Wake methods (screen OFF → ON)

| Method | Works? | Notes |
|---|---|---|
| `am start -n com.miui.calculator/.cal.CalculatorActivity` | ✅ (primary) | binder path; woke when every keyevent failed |
| `cmd notification post -S bigtext -t X tag text` | ✅ for hours, then went dead | most reliable early; likely affected by a user-side notification-wake setting |
| `input keyevent 26/224/82/126` | ❌ always, even with inject permission | MIUI blocks wake-class injected keys |
| `input keyevent 223` (SLEEP) | ✅ | sleep allowed, wake blocked — asymmetric by design |
| `wm dismiss-keyguard` | n/a (doesn't wake) | |

Keep-awake: `input keyevent 24/25` (permission B) resets the sleep timer; otherwise re-issue
`am start` every ~1.5 s. Lit window after wake ≈ 1-3 s ("fast-sleep gremlin") — capture inside it.

## Screencap size oracle (exec-out screencap -p, device 1080x2340)

| Size | Meaning |
|---|---|
| 0 B | transition / secure-surface / command failed → retry |
| **15197 B (exact, recurring)** | display OFF / black lockscreen frame |
| 84-142 KB | lit app content (e.g. Settings, Calculator) |
| ~3.34 MB | lit lockscreen / full-detail screen |

`exec-out screencap -p > file` = single roundtrip, preferred over `shell screencap` + `pull`.

## Bouncer / pattern unlock

- MIUI raises the pattern bouncer on a SLOW drag (~1000 ms) upward; 120 ms flicks are ignored
  (user-confirmed: "ต้องปัดแบบเหมือนลากขึ้นข้างบนประมาณ 1 วินาที").
- Houston-injected swipes NEVER raised it in ~10 attempts across three phases (pre-permission).
  Post-permission effect unverified (screen asleep during tests).
- `wm dismiss-keylock`... `wm dismiss-keyguard` is a no-op on secure locks.
- `CONFIRM_DEVICE_CREDENTIAL` intent, `com.android.settings/.ConfirmLockPassword|Pattern`,
  `Settings$SecurityDashboardActivity` launches: all go BEHIND keyguard (screen unchanged,
  byte-identical 3.346 MB captures).
- Bouncer timeout ≈ 15-30 s. uiautomator dump on lockscreen/bouncer: stale files or
  secure-filtered trees — never ground truth.
- Grid detection (PIL): threshold ladder 160/135/110, region y1150-2200, BFS connected
  components downscaled ×3, area 100-7000 px², fit 3 rows (gap ≤90 px) + 3 cols + spacing
  consistency; keypad map rows top→bottom.
- Draw: `input motionevent DOWN → MOVE× (6 interpolated substeps/segment, ~45 ms) → UP`,
  one continuous gesture, points from vault pattern string (keypad order).
- Proximity was NOT the screen-off cause (dumpsys sensorservice PROXIMITY events = 5.00 = far).

## Wake-method timeline (context for "everything went silent")

1. notification post: woke reliably ~12 attempts (03:00-14:50) → later attempts posted
   ("posting:" output) but wakefulness stayed Asleep.
2. am start: failed to wake early in session → worked ONCE after gate flap → then stopped.
3. Interpretation: user-side settings churn (lock added/removed, dev toggles) changes both the
   inject gate and notification-wake behavior mid-session — always re-probe, never assume yesterday's
   recipe holds.
