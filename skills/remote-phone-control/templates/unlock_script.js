// unlock_script.js — AutoJS6 remote-unlock TEMPLATE (MIUI / stock Android)
// ⚠️ This public copy ships WITHOUT any real unlock pattern.
// Trigger:
//   adb push unlock_script.js /storage/emulated/0/unlock_script.js
//   adb shell am start -a android.intent.action.VIEW \
//     -n org.autojs.autojs6/org.autojs.autojs.external.open.RunIntentActivity \
//     -d file:///storage/emulated/0/unlock_script.js -t text/plain
// Comms: adb shell logcat -d | grep GlobalConsole | grep -oE 'HOUSTON.*'
//
// BEFORE FIRST USE: complete SKILL.md §Unlock workflow step 1 (pointer-location
// calibration) so houston_grid.json exists with real dot coordinates.
// Grid JSON format: {"1":[x,y], "2":[x,y], ... "9":[x,y]}  (keypad positions)

var GRID_FILE = "/storage/emulated/0/houston_grid.json";
var SEQ = "YOUR_PATTERN"; // ⚠️ REPLACE with your own 7-digit keypad pattern:
                          // digits 1-9 in the order the stroke touches them
                          // (keypad layout: 1=top-left … 9=bottom-right).
                          // The placeholder string will never unlock anything.

log("HOUSTON start screen=" + device.isScreenOn() + " pkg=" + currentPackage());

// 1) wake
try { device.wakeUp(); } catch (e) { log("HOUSTON wakeup-fail " + e); }
sleep(900);
log("HOUSTON awake screen=" + device.isScreenOn());

// already unlocked?
if (currentPackage() !== "com.android.systemui") {
    log("HOUSTON already-unlocked pkg=" + currentPackage());
    exit();
}

// 2) user journey step 1: long drag >= 1s, finger never lifted
try {
    gesture(1400, [[540, 2210], [540, 1750], [540, 1300], [540, 950]]);
    log("HOUSTON longdrag-done");
} catch (e) { log("HOUSTON longdrag-fail " + e); }
sleep(800);

// 3) load calibrated grid
var grid = null;
try {
    grid = JSON.parse(files.read(GRID_FILE));
    log("HOUSTON grid-loaded");
} catch (e) { log("HOUSTON grid-missing " + e); }
if (!grid) {
    log("HOUSTON ABORT: run calibration first (SKILL.md unlock workflow step 1)");
    exit();
}

// 4) user journey step 2: drag pattern as one continuous stroke
var pts = [];
for (var i = 0; i < SEQ.length; i++) {
    var p = grid[SEQ.charAt(i)];
    if (!p) { log("HOUSTON ABORT: grid missing digit " + SEQ.charAt(i)); exit(); }
    pts.push([p[0], p[1]]);
}
try {
    gesture(2200, pts);
    log("HOUSTON pattern-drawn");
} catch (e) { log("HOUSTON pattern-fail " + e); }

// 5) verify
sleep(2000);
var pkg = currentPackage();
log("HOUSTON final pkg=" + pkg + (pkg !== "com.android.systemui" ? " UNLOCKED" : " STILL-LOCKED"));
exit();
