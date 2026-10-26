# Grid Detection + Pattern Draw + Capture Recipes

## Capture recipe (lit frame)

```python
def cap_exec(path, tries=5):            # exec-out = 1 roundtrip, most reliable
    for _ in range(tries):
        with open(path, 'wb') as f:
            subprocess.run(["adb","-s",DEV,"exec-out","screencap","-p"],
                           stdout=f, stderr=subprocess.PIPE, timeout=8)
        sz = os.path.getsize(path)
        if sz > 100000: return sz       # real content
        time.sleep(0.35)
    return sz
```
Size legend (this device, 1080x2340):
- `0B` — screencap raced a display transition → retry.
- `~15197B` — screen OFF frame (constant!). Exists even while
  `mWakefulness=Awake` if display never lit.
- `~84–142KB` — app UI (calculator ≈84KB, settings ≈135KB).
- `~3.34MB` — lockscreen / notification panel / heavy UI.
First capture after wake is often the stale OFF frame → loop until >100KB.
While keyguard up with SECURE content, captures occasionally return 0B for a
few seconds — retry rather than conclude failure.

## Grid detection (`detect_grid`)

Goal: 9 dots of the pattern bouncer → keypad-mapped `{digit: (x,y)}`.

Algorithm (pillow + numpy, no scipy):
1. grayscale array; for thr in (160,135,110) × y0 in (1150,1400), region
   y0..2200, x40..W-40;
2. downscale mask by S=3 (`mask[::3,::3]`) so BFS runs on ~1/9 cells;
3. BFS components (deque, 8-neighbour, cap ~900 pts), keep area
   100–7000 (after ×S²) — rings are hollow, area ≈540–1500;
4. cluster centers into 3 rows (y-gap ≤90, row spacing 110–450), then per row
   into 3 columns (x-gap ≤90), require Δx consistency ≤90 across rows;
5. map via keypad grid (row0=top):
   ```
   1(c0,r0) 2(c1,r0) 3(c2,r0)
   4(c0,r1) 5(c1,r1) 6(c2,r1)
   7(c0,r2) 8(c1,r2) 9(c2,r2)
   ```
6. persist `/tmp/grid.json`.

Caveats: it returns None on the LOCKSCREEN (notification text blobs ≈ rows of
small components at y1024–1333 are NOT a grid — spacing/col-split checks reject
them). Do not force-fit; if detection says no-grid on a lit capture, the
bouncer is not showing.

## Dense pattern draw (never lift the finger)

User pattern vault entry, dash order (keypad), e.g. shape "M": `YOUR_PATTERN`.
One continuous gesture — Android pattern view only registers cells passed
through, so interpolate:

```python
pts = [grid[c] for c in seq]                    # 7 dots
path = [pts[0]]
for i in range(1, len(pts)):
    x0,y0 = pts[i-1]; x1,y1 = pts[i]
    for s in range(1, 7):                       # 6 substeps/segment ≈ 25-40px
        path.append((round(x0+(x1-x0)*s/6), round(y0+(y1-y0)*s/6)))
sh("input","motionevent","DOWN", *path[0])
for p in path[1:]: sh("input","motionevent","MOVE", *p); time.sleep(0.045)
sh("input","motionevent","UP", *path[-1])
```
This is the Android-12 equivalent of uiautomator1 `UiDevice.swipe(Point[],
segmentSteps)` (that API no longer exists; SO q/20320186 is the origin of the
dense-segment approach). Requires open grant — first DOWN with
SecurityException ⇒ abort (never send a partial pattern; wrong attempts count
toward lockout).

Verify: sleep 1.5s → `dumpsys window | grep mCurrentFocus`; success =
launcher/app (NOT NotificationShade) → capture `unlocked_home.png`.

## Bouncer-raise: failed inventory (do not retry blindly)

All produced byte-identical or off-state captures — only the user's physical
swipe works:
- `input swipe` fast (120ms) at y=1900/2100/2150/2320/2330
- `input swipe` slow (1000ms, the user-instructed "drag ~1s") at same y's
- dense `input motionevent` UP-drags (24-30 steps, 45-50ms apart), from y=2150
  and y=1750
- `input keyevent 82`, `input keyevent 4` + `cmd statusbar collapse` first
- `am start -a android.settings.LOCK_SCREEN_SETTINGS` / `SECURITY_SETTINGS`
  (activities launch BEHIND keyguard)
- `am start -a android.app.action.CONFIRM_DEVICE_CREDENTIAL`
- `am start -n com.android.settings/.ConfirmLockPassword` / `.ConfirmLockPattern`
  (start ok, no visible UI), `.KeyguardActivity` → Error type 3
- `wm dismiss-keyguard` (runs, no effect while CredentialType=Pattern)

## Live-sync protocol (user-assisted bouncer)

1. Tell the user: type "swiped", hit send, then immediately drag up slowly ~1s and leave the grid on screen
2. On their reply, immediately poll every 1.5s for 40–60s: cap_exec →
   detect_grid → break on hit.
3. Draw + verify + capture in the same run (bouncer auto-hides in ~15-30s;
   volume keyevent as keepalive while grant is open).

## Keeping the screen alive

- `screen_off_timeout=MAX_INT` ⇒ never sleeps by itself; only sleep-keys do.
- While grant open: keepalive thread pressing `keyevent 24` every ~1.3s.
- While grant blocked: nothing to hold it — coordinate with user instead.
