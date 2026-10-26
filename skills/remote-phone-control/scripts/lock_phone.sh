#!/usr/bin/env bash
# lock_phone.sh — turn the screen off (= lock) on the Redmi 9.
# Exit 0 = mScreenState=OFF confirmed; 1 = failed.
# `input keyevent 223` only works while MIUI's INJECT_EVENTS window is open (it flaps),
# so: try it a few times, then fall back to svc power stayon false + short timeout.
set -u
log() { echo "[lock] $*"; }

if ! adb devices | grep -qE '^10\.66\.66\.2:.*device$'; then
    log "no adb device — run unlock_phone.sh first (it scans+connects)"; exit 1
fi

get_state() { adb shell dumpsys display | grep -m1 mScreenState; }

# NOTE on stay_on_while_plugged_in: restoring it (`svc power stayon true`) WAKES the
# display immediately while the phone is on a charger => a "locked" phone comes back lit.
# Strategy: lock leaves stayon=0 (timeout=MAX is restored, so the phone still never
# self-times-out during normal use); unlock_phone.sh puts stayon=7 back once unlocked.

# fast path: SLEEP keyevent (only if injection window is open)
for i in 1 2 3 4; do
    if ! adb shell input keyevent 223 2>&1 | grep -q SecurityException; then
        log "keyevent 223 accepted (attempt $i)"
        sleep 2
        if get_state | grep -q OFF; then log "OFF via keyevent"; exit 0; fi
    fi
    sleep 2
done
log "injection window closed — using stay-on/timeout fallback"

# fallback: allow sleep, force a short timeout
adb shell svc power stayon false >/dev/null 2>&1
adb shell settings put system screen_off_timeout 8000
for i in $(seq 1 14); do
    sleep 5
    if get_state | grep -q OFF; then
        log "OFF via timeout fallback (${i}x5s)"
        adb shell settings put system screen_off_timeout 2147483647
        log "restored timeout=MAX (stayon left at 0 on purpose — unlock restores 7)"
        sleep 1
        get_state | grep -q OFF && exit 0
        log "WARN screen came back ON after timeout restore"; exit 1
    fi
done
log "FAILED — screen still $(get_state)"
adb shell settings put system screen_off_timeout 2147483647
exit 1
