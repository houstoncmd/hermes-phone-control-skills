# Reading app content remotely — unread messages, badges, transcripts

Proven 2026-10-24 in one shot: unlock → open LINE → read **every** unread message (16)
→ report → close apps → empty home → lock. All four goals, one pass.

## 0. Order of operations (the thing that can't be undone)

```
unlock_phone.sh  →  open app  →  HARVEST  →  report to user  →  force-stop apps
                  →  empty home  →  lock_phone.sh
```

Harvest **before** closing apps (force-stop destroys the content) and **before** locking
(a dark/locked screen can't be read). If the user lists "read X then close then lock" in a
random order, silently reorder to this and say so in the report.

## 1. Badge = ground truth for the count

```bash
adb shell uiautomator dump /sdcard/u.xml && adb pull /sdcard/u.xml
python3 scripts/show_rows.py u.xml          # text / content-desc / bounds rows
```

LINE encodes the count in the a11y label: `Chats tab 16 new items`, plus a numeric badge on
the conversation row. **Your report must contain exactly that many items.** Fewer → you
missed scroll frames (stitch again, smaller scroll steps); more → you double-counted a
overlapping frame (dedupe by y+text, as stitch does).

## 2. Two readers, one at a time

| Reader | Wins for | Loses against |
|---|---|---|
| host `uiautomator dump` | list/tab screens, badge, one-shot state | it *seizes the accessibility service* → AutoJS scrolling silently stops working |
| AutoJS6 script (scroll + node dump → `log()` → logcat) | long scrolling transcripts | competing host dumps |

So: scan the list with the host dump, then switch to AutoJS for everything inside the
conversation. Do not interleave.

## 3. Harvest recipe (scroll-frame stitch)

1. `scripts/fire_js.sh harvester.js 20` — the script wakes, taps into the chat (host
   `input tap` may be dead: MIUI injection flaps), then loops: **snapshot nodes → scroll up
   one notch → repeat until the first message / a frame repeats**. Every frame is `log()`ed
   to `GlobalConsole` with a frame marker.
2. Pull once: `adb shell logcat -d | grep GlobalConsole > capX.txt`.
3. `python3 ~/stitch.py capX.txt X` joins frames, dedupes overlapping rows by y+text, and
   prints the stream. Sticky **date headers sit at the top of the viewport** (y≈225) — those
   are your real message dates; timestamps (`9:09 AM`, `11:26 AM`) are per-message.
4. Walk the stream newest→oldest, group by date header, count → compare with the badge.

Autoscroll gotchas on this device: some apps don't advance on `gesture()` from a random
point — scroll from inside the scrollable node's bounds; if a frame repeats twice, the
scroller is dead (usually because a host `uiautomator dump` is holding the service).

## 4. LINE ids (Redmi 9, package `jp.naver.line.android`)

| Thing | Value |
|---|---|
| splash / launcher | `.activity.SplashActivity` |
| chat list (main) | `.activity.main.MainActivity` |
| conversation | `.activity.chathistory.ChatHistoryActivity` |
| separate OA client | `com.linecorp.lineoa` |

Opening a conversation **marks it read immediately** (badge clears). Unavoidable — tell the
user in the report rather than pretending the badge survived.

## 5. Cleanup + verify

```bash
adb shell am force-stop jp.naver.line.android
adb shell pidof jp.naver.line.android        # empty = dead
# recents: HORIZONTAL fling per card, NOT "clear all" (kills WireGuard!)
adb shell input swipe 900 1600 150 1600 80   # repeat for each non-WireGuard card
adb shell dumpsys window | grep mCurrentFocus   # com.miui.home/.launcher.Launcher = home
adb shell ping -c2 10.66.66.2                 # tunnel still alive?
scripts/lock_phone.sh                         # mScreenState=OFF + isKeyguardShowing=true
```

Home is clean when a fresh `uiautomator dump` shows only dock/widget descs
(`Phone`, `Messages`, `Chrome`, `Camera`, `Open App drawer`, clock/weather widget) — no
third-party app rows.

## 6. Reporting style the user expects

Thai, table-or-numbered list newest→oldest, each item = date + time + what it says
(summarised, quote only short key lines), explicit count line ("16 messages — matches the
badge"), and a one-line note for anything irreversible you had to do (e.g. marking read).
Attach proof as `MEDIA:/path` when a screenshot exists.
