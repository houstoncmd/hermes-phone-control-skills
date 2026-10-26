# MIUI Wake / Bouncer Hunting — Evidence Log
Device: Redmi 9 (M2004J19C, lancelot), Android 12 / MIUI 13, lock = **Pattern**, 1080x2340. Date: 2026-10-24.

## Wake behavior (verified)
- `input keyevent 224` (WAKEUP) and `26` (POWER): NO SecurityException after the MIUI security
  toggle, yet screen stays `mWakefulness=Asleep` — MIUI ignores injected wake keys. Don't retry.
- **Works: `cmd notification post -S bigtext -t "Houston" <tag> "text"`** → Awake ~0.7-1.5 s later.
- Display ON window only **~2-5 s** (`dumpsys display | grep mScreenState`), then Asleep again —
  even with `screen_off_timeout=2147483647`.
- `am start` (calculator, Settings intents) while asleep: intent delivered, NO wake, focus unchanged.
- Injecting a tap right after wake extended the ON window to ≥6 s in one run (not yet reproduced
  reliably — always re-check `mWakefulness`/`mScreenState` per step).

## Screencap truth table (this device)
| bytes | meaning |
|---|---|
| 15197 (constant md5) | display OFF — black frame |
| 0 | transition race (silent failure) → retry |
| ~3.34 MB | real lit content (1080x2340 RGBA) |

Recipe: wake → sleep 1.0 → `screencap -p /sdcard/x.png` + `pull`, retry 3-6× at 0.5-0.7 s until >100 KB.

## Bouncer trigger attempts — ALL FAILED (focus stayed `NotificationShade`, no 3×3 grid in captures)
1. `input swipe 540 1900 540 500 150` (panel swipe-up)
2. `input keyevent 4` + `cmd statusbar collapse` + swipe `540 2050 → 600`
3. `input keyevent 82` (MENU)
4. extreme-bottom gesture swipe `540 2330 → 1200` (gesture-nav area)
5. slow mid swipe `540 2100 → 700` 400 ms
6. `am start -a android.settings.LOCK_SCREEN_SETTINGS` and `SECURITY_SETTINGS` → intent
   STARTS but launches **behind** keyguard (correct security), never focused.

Notes:
- `uiautomator dump` on lockscreen returns only the non-secure tree (`notification_stack_scroller`,
  `miui_keyguard_clock_container [0,0][1080,562]`, `keyguard_bottom_area [0,2110][1080,2134]`)
  and served the SAME stale hierarchy across gestures → screenshots are ground truth.
- `dumpsys window windows` shows no separate bouncer window (it lives inside NotificationShade).
- `MiuiKeyguardPictorialWallpaper` present = MIUI Lock Screen Magazine may hijack gestures;
  user can disable in ตั้งค่า → ล็อกหน้าจอ.
- `dumpsys lock_settings` → `CredentialType: Pattern`; `cmd lock_settings get-disabled` →
  `IllegalArgumentException: Credential can't be null or empty` → **no CLI bypass** (stops here).

## Resume plan (session paused here — user asked to open pattern screen manually)
1. User opens the pattern screen manually (~10 s) and leaves it.
2. Houston: capture (retry recipe) → `scripts/find_pattern_grid.py <png>` → 3×3 centers
   (rows top→bottom = keypad 1-2-3 / 4-5-6 / 7-8-9).
3. Draw ONE continuous gesture: `input motionevent DOWN x y` → `MOVE` ×6 → `UP`
   (**UNTESTED on this device**; fallback = raw `sendevent` touch sequence via /dev/input,
   needs `getevent -pl` coordinate ranges).
4. Verify unlock: `dumpsys window | grep mCurrentFocus` must be `com.miui.home/...Launcher`
   (or last app) — NOT `NotificationShade`. Then capture home → MEDIA → `input keyevent 223` relock.
5. Safety: only draw after the grid detector validates 9 dots (Android locks out after 5 wrong
   patterns: 30 s → escalating). Pattern credential is in vault.json
   entry "Phone Lock (Redmi 9 / Houston remote)" — never echo.
