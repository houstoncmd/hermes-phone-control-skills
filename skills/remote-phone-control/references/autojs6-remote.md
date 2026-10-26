# AutoJS6 as Remote Actuator — Trigger, Scripting, Comms

AutoJS6 (`org.autojs.autojs6`) is installed on the phone with its accessibility service
`org.autojs.autojs.core.accessibility.AccessibilityServiceUsher` enabled
(`settings get secure accessibility_enabled` → 1, entry in
`enabled_accessibility_services`). Its accessibility status is what lets scripts dispatch
gestures even when adb `input` injection is blocked by MIUI.

## Trigger (fully autonomous from Houston)

```bash
adb push my.js /storage/emulated/0/my.js      # shell CAN write sdcard root
adb shell am start -a android.intent.action.VIEW \
  -n org.autojs.autojs6/org.autojs.autojs.external.open.RunIntentActivity \
  -d file:///storage/emulated/0/my.js -t text/plain
```

Manifest filter (verified): action VIEW/EDIT, scheme `file`/`content`,
types `text/plain` + `application/x-javascript`. The app CAN read the file through the
intent even though scoped storage blocks its own `files.write()` to sdcard root.

Other components present (not yet exercised): `ImportIntentActivity`, `EditIntentActivity`,
`ShortcutActivity`, Tasker plugin (`external.tasker.PluginActivity`,
`FireSettingReceiver`), `StaticBroadcastReceiver` (boot/power/package events),
quick-settings tile `LayoutHierarchyTile`, `NotificationListenerService`.

## Comms channel: logcat (NOT files)

```bash
adb shell logcat -c
# ... push + trigger ...
sleep ~12-35   # script runtime observed: 15-32s
adb shell logcat -d | grep GlobalConsole | grep -oE 'HOUSTON.*'
```

- Script logs print as `D GlobalConsole: .../D: <msg>`; prefix every message with a
  unique token (`HOUSTON`) for grepping.
- `files.write("/storage/emulated/0/...")` throws (scoped storage) — do not use files for
  results; log them instead.
- `exit()` may print a harmless `System.err` stack through `Global.exit` — ignore it.

## API proven to work on this device

```js
log("...");                       // → logcat GlobalConsole
device.wakeUp();                  // ✅ wakes screen even from off (try/catch anyway)
device.isScreenOn();  device.width;  device.height;   // 1080x2340
gesture(1400, [[540,2210],[540,1750],[540,1300],[540,950]]);  // ONE continuous stroke,
      // duration ms, never lifts — matches user journey "ลาก ≥1วิไม่ปล่อยมือ"
currentPackage();                 // success check: != "com.android.systemui"
className("...").findOne(ms);  classNameMatches("...").find();
```

## Hard limits on this MIUI

- **Keyguard/bouncer nodes are invisible**: `classNameMatches(".*").find()` returns 0 nodes
  on the lockscreen → cannot read PatternView bounds; pattern strokes must use fixed
  coordinates calibrated from a physical draw (pointer-location overlay trick — see SKILL.md
  §Unlock workflow).
- Whether `gesture()` raises the bouncer by itself is UNPROVEN (drags ran while locked,
  no positive bouncer detection possible from outside). Plan for the semi-auto fallback:
  user raises bouncer → Houston fires pattern-draw script.
- Never blind-guess dot coords while a bouncer is showing (wrong attempts → lockout).

## Script skeleton

See `templates/unlock_script.js` in this skill: wake → long drag (≥1s, no lift) →
read calibrated grid JSON → draw pattern stroke → verify `currentPackage()` → log stages.
Grid JSON is pushed to `/storage/emulated/0/houston_grid.json` after calibration.
