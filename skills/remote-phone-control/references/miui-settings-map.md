# MIUI 13 (Redmi 9, Global V13.0.2.0.SJCMIXM) — settings menu map

For "which menu do I need" questions. Paths are from live UI dumps (uiautomator). Launch a Settings
screen with `am start -n com.android.settings/.Settings$<X>Activity` — but see pitfall #21,
many MIUI sub-activities are NOT exported; navigate the UI when in doubt.

| User ask | Menu path | Activity / notes |
|---|---|---|
| Always-on display (AOD) on/off | Settings → Lock screen → section **"WHEN TO SHOW"** → Always-on display | Switch ~x853-1002 on 1080-wide; row title opens style sub-page. `AODSettingActivity` + `display.AODStyleActivity` NOT exported. State = switch `checked`; no `doze_always_on` key. AOD strings live in `com.android.thememanager`. |
| Screen timeout (why won't the screen go dark) | Settings → Display → **Sleep** | ⚠️ On this phone `screen_off_timeout=2147483647` + `stayon=7` is **Houston's own remote-control config**, not AOD — tell the user before they "fix" it. `Settings$DisplaySettingsActivity` exported ✓ |
| Lock screen extras (signature, wallet, device controls) | Settings → Lock screen → section "WHAT TO SHOW" | `Settings$LockScreenSettingsActivity` exported ✓ |
| VPN / Always-on VPN | Settings → Connection & sharing → VPN → ⚙️ next to WireGuard | See "Always-on VPN" section in SKILL.md — adb write blocked, UI only |
| Notification per-app mute | Settings → Notifications → [app] | Or remotely via `appops set <pkg> POST_NOTIFICATION ignore` |
| Accessibility / AutoJS6 re-enable | Settings → Additional settings → Accessibility → Downloaded apps → AutoJS6 | Manual-only (pitfall #20) |

**Settings search shortcut is dead**: `--es ":settings:search_results_activity_key"` extras do
nothing from adb. To enumerate real activity names use
`unzip -p <settings.apk> AndroidManifest.xml | tr -d '\0' | grep -oE 'com.android.settings/[A-Za-z0-9_.$]+'`
— the manifest is one giant line, so grep for a NAME PATTERN, never dump it whole (blows context).

**Dump tips**: `exec-out uiautomator dump /dev/tty` works even with AutoJS6 service OFF (host
side), but only sees the CURRENT scroll position — scroll with AutoJS gesture (needs service
up) or expect partial views. Fresh state: `am force-stop com.android.settings; am start -a
android.settings.SETTINGS` resets scroll to top (a plain `am start` just resumes the old
scrolled position).
