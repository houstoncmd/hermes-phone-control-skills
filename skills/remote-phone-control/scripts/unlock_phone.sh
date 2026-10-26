#!/usr/bin/env bash
# unlock_phone.sh — one-shot remote unlock of the Redmi 9 (calibrated AutoJS replay).
# Usage: unlock_phone.sh            # unlock if locked, report result
#        unlock_phone.sh --force    # run gestures even if it looks unlocked (re-test)
# Exit 0 = unlocked (or already unlocked); 1 = failed / not connected.
set -u
FORCE="${1:-}"
PHONE=10.66.66.2
SCRIPT=$HOME/.hermes/skills/devops/remote-phone-control/scripts
LOCAL_JS=$HOME/unlock_script.js
REMOTE_JS=/storage/emulated/0/unlock_script.js
log() { echo "[unlock] $*"; }

# 1) tunnel
if ! ping -c2 -W2 "$PHONE" >/dev/null 2>&1; then
    log "TUNNEL DOWN — ask user: open WireGuard app + battery 'No restrictions' + Always-on VPN"; exit 1
fi

# 2) adb connect (ports rotate!)
if ! adb devices | grep -q "^$PHONE:.*device$"; then
    log "no adb device — scanning ports"
    OUT=$(timeout 90 python3 "$SCRIPT/scan_connect.py" "$PHONE" 2>&1 | tail -3)
    echo "$OUT"
    if ! adb devices | grep -q "^$PHONE:.*device$"; then
        log "ADB UNREACHABLE — likely needs one manual unlock after reboot (wireless debug), or re-pair"; exit 1
    fi
fi

# 3) sync script to phone (encoded PATH lives inside the .js)
if ! cmp -s "$LOCAL_JS" <(adb exec-out cat "$REMOTE_JS" 2>/dev/null); then
    log "pushing unlock_script.js"
    adb push "$LOCAL_JS" "$REMOTE_JS" >/dev/null || { log "push failed"; exit 1; }
fi

# 4) state probe
STATE=$(adb shell dumpsys display | grep -m1 mScreenState)
KG=$(adb shell dumpsys window | grep -m1 isKeyguardShowing)
log "state: $STATE | $KG"
# keyguard only reports true once the display is awake; while OFF it reads false,
# so "screen OFF" must also count as "needs unlock" (the .js re-checks pkg after wake).
if [ "$FORCE" != "--force" ] && ! echo "$STATE" | grep -q OFF && echo "$KG" | grep -q "false"; then
    log "ALREADY UNLOCKED — nothing to do (use --force to re-test)"; exit 0
fi

# 5) fire AutoJS
adb shell logcat -c
adb shell am start -a android.intent.action.VIEW \
    -n org.autojs.autojs6/org.autojs.autojs.external.open.RunIntentActivity \
    -d "file://$REMOTE_JS" -t text/plain >/dev/null 2>&1 || { log "intent failed"; exit 1; }
log "script fired — polling for HOUSTON FINAL (was fixed sleep 18s)"
# poll instead of blind sleep: the marker appears ~2.5s after the engine starts,
# so the whole unlock drops from ~22s to ~6s when the gestures succeed first try.
FOUND=""
for _ in $(seq 1 100); do           # up to 30s
    if adb shell logcat -d 2>/dev/null | grep -q 'HOUSTON FINAL'; then
        FOUND=1; break
    fi
    sleep 0.3
done
[ -n "$FOUND" ] || log "no HOUSTON FINAL within 30s — reading whatever we got"

# 6) read result
adb shell logcat -d | grep GlobalConsole | grep -oE 'HOUSTON.*' | sed 's/^/[phone] /'
FINAL=$(adb shell logcat -d | grep GlobalConsole | grep -oE 'HOUSTON FINAL.*' | tail -1)
KG2=$(adb shell dumpsys window | grep -m1 isKeyguardShowing)

if echo "$KG2" | grep -q "false" && adb shell dumpsys display | grep -m1 mScreenState | grep -q ON; then
    log "SUCCESS — keyguard gone, screen on"
    # phone is awake again => safe to put the charging-stay-awake preference back
    adb shell svc power stayon true >/dev/null 2>&1
    log "restored stayon=7 (timeout=$(adb shell settings get system screen_off_timeout | tr -d '\r'))"
    adb exec-out screencap -p > $HOME/unlock_proof.png 2>/dev/null
    log "proof: $HOME/unlock_proof.png ($(stat -c%s $HOME/unlock_proof.png) bytes)"
    exit 0
fi
log "FAILED — $KG2 | $FINAL"
log "fallback: ask the user to raise the bouncer, then re-run (--force draws pattern only)"
exit 1
