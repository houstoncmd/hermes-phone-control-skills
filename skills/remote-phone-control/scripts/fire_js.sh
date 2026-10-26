#!/usr/bin/env bash
# fire_js.sh — push an AutoJS6 script to the phone, fire it via the VIEW intent, print its
# GlobalConsole log.
#
#   bash scripts/fire_js.sh <script.js> [wait_seconds]     # default wait 6s
#
# Exit codes: 0 = ran AND logged at least one HOUSTON marker
#             2 = no adb device   3 = push failed   4 = intent failed
#             5 = ran but no HOUSTON marker (script bug / died early)
set -uo pipefail

JS="${1:?usage: fire_js.sh <script.js> [wait_seconds]}"
WAIT="${2:-6}"
BASE="$(basename "$JS")"
DEST="/storage/emulated/0/$BASE"
AUTOJS_PKG="org.autojs.autojs6"

adb get-state >/dev/null 2>&1 || { echo "NO_DEVICE"; exit 2; }
[ -f "$JS" ] || { echo "NO_SUCH_FILE $JS"; exit 3; }

adb shell logcat -c 2>/dev/null
adb push "$JS" "$DEST" >/dev/null 2>&1 || { echo "PUSH_FAILED $DEST"; exit 3; }

OUT="$(adb shell am start -a android.intent.action.VIEW \
  -n "$AUTOJS_PKG/org.autojs.autojs.external.open.RunIntentActivity" \
  -d "file://$DEST" -t text/plain 2>&1)"
case "$OUT" in
  *Error*|*Exception*|*not\ found*) echo "FIRE_FAILED: $OUT"; exit 4 ;;
esac

sleep "$WAIT"
LOG="$(adb shell logcat -d 2>/dev/null | grep GlobalConsole || true)"
if [ -z "$LOG" ]; then
  echo "NO_LOG (script may not be running — is $AUTOJS_PKG alive?)"
  exit 5
fi
echo "$LOG" | grep -E 'HOUSTON' || echo "$LOG"
echo "$LOG" | grep -qE 'HOUSTON' && exit 0 || exit 5
