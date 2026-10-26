# MIUI ADB Restrictions — Field Notes (Redmi 9 / lancelot, M2004J19C)

Verified 2026-10-24 on the user's Redmi 9 (WireGuard 10.66.66.2, adb over
wireless debugging). Every item below was reproduced live, not assumed.

## 1. Input injection blocked while locked

```
$ adb shell input swipe 540 2000 540 800 200
java.lang.SecurityException: Injecting to another application requires
INJECT_EVENTS permission
    at com.android.server.input.InputManagerService.injectInputEventInternal(...)
```

Applies to `input tap`, `input swipe`, `input keyevent` — including
`KEYCODE_WAKEUP` (224) and `KEYCODE_POWER` (26). So you can neither wake the
screen nor draw an unlock pattern via `input` while the device is locked.

**One-time user fix:** Settings → Additional settings → Developer options →
enable **"USB debugging (Security settings)"** (MIUI shows the literal Thai translation of this label).
Some MIUI builds additionally require confirming with the Mi Account password.
After that, injection works even on the lockscreen.

Intermittency note: injection *sometimes* succeeds for a command issued right
after `svc power stayon true` while the display is transitioning ON — do not
rely on this; treat any INJECT_EVENTS error as "locked + toggle off".

## 2. Reliable screen wake (no `input` needed)

`input keyevent 26` / `224` fail with the error above when locked. Working
sequence:

```bash
adb shell svc power stayon true      # wakes AND holds the display
adb shell dumpsys display | grep -m1 mState=     # expect: mState=ON
```

`svc power stayon true` writes `stay_on_while_plugged_in=7` (AC|USB|Wireless)
and reliably flips `mState=OFF → ON` within ~2 s even from deep sleep. Poll
`dumpsys power | grep mWakefulness=` too (`Awake`).

`cmd power wake` does not exist on this build ("Unknown command: wake").

## 3. `screencap` lies when the display is off

- Display OFF → `screencap -p` returns a **constant 15,197-byte all-black PNG**
  (identical sha256 across captures) — it looks like a valid file, it is not.
- Deeper sleep → **0 bytes, RC=1**, no stderr message at all.

Verification gate before trusting any capture:

```bash
adb shell dumpsys display | grep -m1 mState=      # must be mState=ON
adb shell screencap -p /sdcard/x.png && adb shell ls -la /sdcard/x.png
# real UI screenshot on this 1080x2340 device ≈ 3.7 MB
```

Prefer `screencap` to a file + `adb pull` over `adb exec-out screencap -p` —
the exec-out pipe silently yields 0 bytes in the failure cases.

## 4. Settings writes blocked (global/secure)

```
$ adb shell settings put global device_name MicrowareMobile
java.lang.SecurityException: Permission denial: writing to settings requires:
android.permission.WRITE_SECURE_SETTINGS
```

- `settings put global ...` and `settings put secure ...` → blocked.
- `settings put system ...` → **works** (e.g. `screen_off_timeout 60000`).
- `content update`/`content call` on `content://settings/global` → also blocked
  (SQL-syntax error surfaces first, but it is the same wall).
- `setprop persist.sys.device_name` / `net.hostname` → "Failed to set property".

Consequence: **renaming the device (global `device_name`) cannot be done via
ADB on MIUI** — it needs the Settings UI (About phone → Device name), which in
turn needs the unlock+injection fix from §1.

## 5. MIUI proximity screen-on guard

`settings get global enable_screen_on_proximity_sensor` → `1`. Effect: the
display blanks again within seconds of waking and a
`ScreenOnProximitySensorGuide` window takes focus
(`dumpsys window | grep mCurrentFocus`). Cannot be disabled via ADB (§4).
Workaround: re-run `svc power stayon true` before each burst of commands and
act within the ON window.

## 6. Rootless credential control via `locksettings`

`adb shell locksettings` works without root on this device and accepts the
stored pattern directly:

```bash
P=$(tr -d '-' < /tmp/.lk)     # vault stores keypad 1-9 in DASH order: "YOUR_PATTERN"
adb shell locksettings verify --old "$P"          # → "Lock credential verified successfully"
adb shell locksettings set-pattern "$P"           # re-set after a test
adb shell locksettings clear --old "$P"           # remove credential
adb shell locksettings set-disabled --old "$P" true   # disable keyguard entirely
adb shell locksettings get-disabled --old "$P"        # → true/false
```

- Passing the pattern WITH dashes → `IllegalArgumentException: row must be in
  range 0-2`. **Strip dashes.**
- `--old` must precede the value: `set-disabled --old "$P" true`, not
  `set-disabled true --old "$P"` (the latter → "Credential can't be null").
- `set-pattern` **echoes the pattern back** in its stdout
  (`Pattern set to 'YOUR_PATTERN'`) — suppress or filter before anything logs it.
- Even with credential cleared AND keyguard disabled, MIUI keeps
  `mDreamingLockscreen=true` and focus on `NotificationShade` until the display
  is actually woken — do not conclude the unlock failed from those flags alone.

**Restore protocol (mandatory if you cleared/disabled for a test):**

```bash
adb shell locksettings set-pattern "$P"
adb shell locksettings verify --old "$P"      # must succeed
adb shell locksettings get-disabled --old "$P" # must be false
```

Vault entry: site_name **"Phone Lock (Redmi 9 / Houston remote)"**, url
`device: lancelot (M2004J19C)`, username "unlock pattern (keypad 1-9, dash
order)". Never echo the pattern in chat — read it to a 0600 temp file
(`open('/tmp/.lk','w')` + `os.chmod`), `tr -d '-'` it into the command, delete
the temp file when done.

## 7. Misc gotchas hit during this session

- `scrcpy 1.25` has **no `--turn-screen-on`** (added in 2.x) and
  `--no-display` requires `--record` or `--v4l2-sink` — it errors out otherwise.
- `adb shell su -c id` → "su: inaccessible or not found" (not rooted).
- `wm dismiss-keyguard` silently no-ops on a pattern-locked MIUI keyguard.
- `am start -a android.media.action.STILL_IMAGE_CAMERA` does NOT wake the
  display on this build.
- `svc power stayon true` is the only waker that worked consistently; battery
  was at 85% / charging, so the "while plugged in" condition was satisfied —
  on battery alone it may not hold the screen.
