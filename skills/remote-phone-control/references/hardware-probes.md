# Hardware capability probes via adb (no root, no spec sheet)

When the user asks "does this device have feature X" (IR blaster, NFC, FM radio, etc.), prove it from
the device itself — spec sites lie about regional variants. All commands run as `adb shell`
(uid 2000), no root needed for reads.

## Evidence ladder (run in order, strongest signals first)

1. **Device-tree node + bound driver** = hardware actually present in the PCB variant:
   `ls /proc/device-tree | grep -i <thing>` → then `ls -l /sys/bus/platform/devices/<node>/driver`
   (a `driver ->` symlink = probed & bound). Read DT props with `od -c` (plain `cat` prints
   nothing — props are NUL-terminated, and shell `cat` of DT files often looks empty).
2. **Char device**: `ls -l /dev/<thing>` — note perms; `system system` 0660 means shell
   CANNOT open it (reads/writes → Permission denied) even though hardware exists.
3. **Kernel framework**: `ls /sys/class/rc`, `/dev/lirc*` (Linux IR), `getevent -pl` (input).
   Empty does NOT disprove hardware — vendor HALs often bypass these.
4. **Framework feature flags**: `pm list features | grep -i <thing>` — e.g.
   `android.hardware.consumer_ir`. **Absence is weak evidence**: Xiaomi MTK ROMs omit
   `consumer_ir` even with working IR TX (they drive it through their own HAL, not
   `ConsumerIrManager`).
5. **Vendor app presence** (weak, corroborating): e.g. Mi Remote =
   `com.duokan.phone.remotecontroller` (note: ships as `/data/app/XMRemoteController`, so
   `pkgFlags` shows no SYSTEM even when preinstalled).

## Worked example — Redmi 9 (lancelot / M2004J19C) IR blaster = PRESENT

| Probe | Result |
|---|---|
| `/proc/device-tree/irtx_pwm` (pinctrl, pwm_ch, pwm_data_invert) | ✅ exists |
| `/sys/bus/platform/devices/irtx_pwm/driver -> .../mt_irtx` | ✅ bound |
| `/dev/irtx` (`crw-rw---- system system`, 490,0) | ✅ exists, shell denied |
| `pm list features \| grep consumer_ir` | ❌ not declared (normal for Xiaomi MTK) |
| Mi Remote `com.duokan.phone.remotecontroller` v6.2.9M | ✅ installed |

**Drive test from adb is impossible** (`/dev/irtx` = system-only, no root) → tell the user to
test in Mi Remote and verify with **another phone's camera** (digital sensors see IR).

## Other quick checks on this phone

- NFC: `/proc/device-tree/irq_nfc` + `pm list features | grep nfc`; toggle via
  `com.android.settings/.Settings$MiuiNfcActivity`.
- Sensors: `ls /sys/class/sensors` (MTK exposes them all).
- SoC/variant: `getprop ro.product.model`, `ro.product.marketname`, `ro.build.version.incremental`
  (this unit: MIUI Global `V13.0.2.0.SJCMIXM`).
