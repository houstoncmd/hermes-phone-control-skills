# MicrowareMobile (Redmi 9) — device card & session notes

Current working device behind the Discord channel for phone commands.

## Identity
- Model: Xiaomi Redmi 9, `M2004J19C`, codename **lancelot** (`lancelot_global`), 1080×2340.
- Displayed name: was `Redmi 9` in `settings get global device_name` — user asked (2026-10-24) to rename to **MicrowareMobile**. NOT yet done: MIUI blocks direct writes (see pitfalls in SKILL.md); requires UI rename after the user unlocks the phone (Settings → About phone → Device name), then verify with `settings get global device_name`.
- Lock: secure pattern lock. ADB cannot dismiss it; user must unlock manually before any UI automation.

## Transport (differs from the Tailscale path in the main skill)
Connected over **WireGuard**, not Tailscale: peer `10.66.66.2`, adb endpoint `10.66.66.2:35669` (port changes when wireless debugging toggles/reboots — read it fresh from the phone's Wireless debugging screen each session).
- `adb devices -l` shows: `10.66.66.2:35669 device ... product:lancelot_global model:M2004J19C`.
- VPN latency ~278 ms RTT — add `sleep 2-3` after input events before capturing/UI-dumping.

## Verified-working commands on this device
- `adb exec-out screencap -p > file.png` (black if display off — check first)
- `adb shell am start -a android.settings.DEVICE_INFO_SETTINGS` → opens Settings$MyDeviceInfoActivity (lands behind keyguard if locked)
- `adb shell svc power stayon true` (does not wake a sleeping screen by itself here)
- `adb shell settings get global device_name` (read OK; write blocked)

## Blocked on this device
- `settings put global device_name` → SecurityException (WRITE_SECURE_SETTINGS)
- `setprop net.hostname` / `setprop persist.sys.device_name` → fail (no root; `su` not present)
- `input keyevent` while locked → SecurityException (INJECT_EVENTS)
- `cmd power wake` → Unknown command
- `input text` for Thai → not supported (ASCII-only, per main skill)
