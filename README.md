# 📱 Android Remote-Control Skills (Hermes Agent)

ชุดสกิล (skill) สำหรับ **สั่งงาน/ดูหน้าจอ/ปลดล็อกโทรศัพท์ Android จากระยะไกล** ผ่านเซิร์ฟเวอร์ Linux (VPS)
ที่รัน Hermes Agent (by Nous Research) — ทดสอบจริงบน MIUI (Redmi 9) และ Stock Android (Moto G9 Plus)

> ⚠️ **Repo นี้เป็น PUBLIC** — ทุกไฟล์ถูกตรวจและปกปิดความลับแล้ว:
> **ไม่มีรหัสผ่าน ไม่มี unlock pattern ไม่มี private key ไม่มี IP เซิร์ฟเวอร์จริง ไม่มีอีเมลจริง**
> ดูหัวข้อ [สิ่งที่ถูกปกปิด](#-สิ่งที่ถูกปกปิด-redaction) สำหรับรายการครบทุกจุด

---

## 📦 ภายใน repo นี้

| โฟลเดอร์ | คืออะไร | เมื่อไหร่ใช้ |
|---|---|---|
| [`skills/remote-phone-control`](skills/remote-phone-control/) | สกิลหลัก — **WireGuard tunnel + adb + AutoJS6** ครอบคลุมการปลดล็อก, อ่านหน้าจอ, สั่งแตะ/ลาก, แจ้งเตือน, watchdog | ต้องการควบคุมจริงจังบนเครื่อง MIUI (ที่ `input` ของ adb ถูกบล็อก) |
| [`skills/android-remote-control`](skills/android-remote-control/) | สกิลรอง — **ADB ผ่าน Tailscale** + fallback อุโมงค์ Termux (no root) + สรุปข้อจำกัด MIUI | เริ่มต้นจากศูนย์, เครื่อง stock Android, หรือไม่มี WireGuard |

โครงสร้างสกิลตามแบบ Hermes Agent (Hermes จะโหลด `SKILL.md` + `references/` + `scripts/` + `templates/` ให้เอง)

```
skills/
├── remote-phone-control/
│   ├── SKILL.md                 ← คู่มือหลัก (state จริง, ขั้นตอน, pitfalls)
│   ├── references/*.md          ← MIUI injection matrix, การอ่านเนื้อหาแอป, เมนู MIUI, hardware probes
│   ├── scripts/*.sh, *.py       ← unlock/lock, port scan, fire_js, notifications, watchdog
│   └── templates/unlock_script.js
└── android-remote-control/
    ├── SKILL.md
    └── references/*.md          ← MIUI ADB restrictions, device card
```

---

## 🏗️ สถาปัตยกรรม

```
┌────────────────────┐        WireGuard (split tunnel)        ┌─────────────────────────┐
│  Android phone     │  10.66.66.0/24, UDP 51820             │  Linux VPS (Hermes)     │
│  • WireGuard app   │ ◄───────────────────────────────────► │  • wg0 10.66.66.1/24    │
│  • Wireless debug  │   adb pair / adb connect (TCP)        │  • adb, python3         │
│  • AutoJS6         │                                       │  • Hermes Agent (AI)    │
└────────────────────┘                                       └─────────────────────────┘
```

* **อุโมงค์ WireGuard** = ช่องทางเดียวที่เซิร์ฟเข้าถึงโทรศัพท์ได้ (ไม่เปิดพอร์ตใดสู่อินเทอร์เน็ตสาธารณะ)
* **adb over wireless debugging** = พอร์ตจะ **สุ่มเปลี่ยนทุกครั้ง** ที่เปิด/ปิดหรือรีบูต → ต้องสแกนใหม่เสมอ
* **AutoJS6 (accessibility service)** = แขนขาที่ใช้แตะ/ลาก/ปลดล็อกจริง
  (บน MIUI คำสั่ง `input tap/swipe` ของ adb ถูกบล็อกด้วย `INJECT_EVENTS` — ห้ามพึ่งพา)

---

## 🚀 เริ่มต้นใช้งาน

### 1) ฝั่งเซิร์ฟเวอร์ (VPS)

```bash
sudo apt-get update && sudo apt-get install -y adb wireguard qrencode python3

# สร้าง key pair ของเซิร์ฟเวอร์ (ห้ามแชร์ private key)
wg genkey | tee /etc/wireguard/server.key | wg pubkey > /etc/wireguard/server.pub

# /etc/wireguard/wg0.conf  (แก้ YOUR_VPS_PUBLIC_IP เป็น IP จริงของคุณ)
#   [Interface]
#   PrivateKey = <server private key>
#   Address    = 10.66.66.1/24
#   ListenPort = 51820
#   PostUp   = iptables -A FORWARD -i wg0 -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
#   PostDown = iptables -D FORWARD -i wg0 -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE

sudo systemctl enable --now wg-quick@wg0
sudo ufw allow 51820/udp          # + 22/tcp ตามนโยบายของคุณ
```

> สคริปต์พร้อมใช้: [`skills/remote-phone-control/scripts/wg_setup.sh`](skills/remote-phone-control/scripts/wg_setup.sh)

### 2) เพิ่มโทรศัพท์เป็น peer

```bash
wg genkey > /tmp/phone.priv; wg pubkey < /tmp/phone.priv > /tmp/phone.pub; wg genpsk > /tmp/phone.psk

# เพิ่ม [Peer] ใน wg0.conf แล้ว apply โดยไม่ restart (เพียร์อื่นไม่หลุด)
sudo wg set wg0 peer "$(cat /tmp/phone.pub)" preshared-key /tmp/phone.psk allowed-ips 10.66.66.2/32
```

สร้างไฟล์ config ฝั่งโทรศัพท์ (⚠️ **ส่งทางอีเมล/ช่องทางส่วนตัวเท่านั้น ห้ามวางในแชต**):

```ini
[Interface]
PrivateKey = <phone private key>
Address    = 10.66.66.2/32
DNS        = 1.1.1.1, 8.8.8.8

[Peer]
PublicKey  = <server public key>
PresharedKey = <psk>
AllowedIPs = 10.66.66.0/24          # SPLIT TUNNEL: เน็ตทั่วไปออกมือถือเอง (ค่าเริ่มต้นที่แนะนำ)
Endpoint   = YOUR_VPS_PUBLIC_IP:51820
PersistentKeepalive = 25
```

```bash
qrencode -t ansiutf8 < wg-phone.conf   # ให้มือถือสแกนจากหน้าจอ หรือส่งไฟล์ .conf
```

### 3) ฝั่งโทรศัพท์ (ผู้ใช้ทำครั้งเดียว)

1. ติดตั้งแอป **WireGuard** → import (สแกน QR) → เปิดสวิตช์
2. ตั้งค่า → แบตเตอรี่ → แอป WireGuard → **ไม่มีข้อจำกัด (No restrictions)**
3. ตั้งค่า → เชื่อมต่อและแชร์ → VPN → ⚙️ ข้าง WireGuard → เปิด **"VPN เสมอเปิดอยู่"** ( Always-on VPN )
4. เปิด **Developer options** (ตั้งค่า → เกี่ยวกับโทรศัพท์ → เวอร์ชันซอฟต์แวร์ → แตะ "เลขเวอร์ชัน" 7 ครั้ง)
   → เปิด **การดีบักแบบไร้สาย (Wireless debugging)**
5. ติดตั้ง **AutoJS6** (F-Droid/GitHub) → ตั้งค่า → เพิ่มเติม → การเข้าถึง → บริการที่ติดตั้ง → เปิด **AutoJS6**

### 4) เชื่อมต่อ adb (ต้องทำใหม่ทุกครั้งที่พอร์ตหมุน)

```bash
ping -c2 10.66.66.2                                    # tunnel ต้องทำงานก่อน
python3 scripts/scan_connect.py 10.66.66.2             # สแกนพอร์ตทั้งหมด + adb connect ให้เอง
adb devices                                             # ต้องขึ้น <ip>:<port> device
```

จับคู่ครั้งแรก (ต้องส่ง **เลข 6 หลัก** จากหน้าจอมือถือภายใน ~2 นาที):

```bash
adb pair 10.66.66.2:<pair-port> <6-digit-code>
```

> 📌 กติกา Android: **หลังรีบูต wireless debugging จะปิดจนกว่าจะปลดล็อกหน้าจอ 1 ครั้ง**
> → สแกนว่างแต่ ping เข้า = ขอให้ปลดล็อก/เปิดสวิตช์ ไม่ใช่ re-pair

---

## 🎮 คำสั่งใช้งานจริง

| งาน | คำสั่ง |
|---|---|
| ปลดล็อกหน้าจอ (อัตโนมัติ) | `scripts/unlock_phone.sh` (exit 0 = สำเร็จ) — ลองใหม่: `--force` |
| ล็อกหน้าจอ | `scripts/lock_phone.sh` |
| สแกนพอร์ต + ต่อ adb | `scripts/scan_connect.py <tunnel-ip>` |
| ยิงสคริปต์ AutoJS6 + อ่านผล | `scripts/fire_js.sh myscript.js` (ผลลัพธ์อ่านจาก logcat tag `GlobalConsole`) |
| เปิด/ปิดการแจ้งเตือนแอป | `scripts/app_notifications.py off\|on\|status [--apps shopee,tiktok]` |
| แปลง dump XML เป็นตารางอ่านง่าย | `scripts/show_rows.py u.xml` |
| Watchdog อุโมงค์ 2 เครื่อง (เงียบเมื่อปกติ) | `scripts/mw_watchdog.py` (รันผ่าน cron แบบ `no_agent=True`) |
| สกรีนช็อต → ส่งให้ดู | `adb exec-out screencap -p > shot.png` แล้วส่งไฟล์ (ตรวจขนาด: `>100KB` = ภาพจริง) |
| ดูว่าแอปไหนอยู่หน้าจอ | `adb shell dumpsys window \| grep mCurrentFocus` |

ลำดับการทำงานที่ถูกต้อง (สำคัญมาก — ทำผิดแล้วข้อมูลหาย):

```
unlock → เปิดแอป → เก็บข้อมูล/อ่าน → รายงาน → ปิดแอป → หน้าโฮม → lock
```

---

## 🔐 ปรับใช้กับโทรศัพท์ของคุณเอง (ใส่ความลับของคุณเอง)

repo นี้ไม่มีค่าจริง คุณต้องใส่เองในเครื่องของคุณเท่านั้น:

1. **Unlock pattern**
   * เก็บไว้ใน vault ของ Hermes (เช่น `~/.hermes/data/vault.json` entry `Phone Lock ...`)
     หรือไฟล์ `0600` บนเครื่อง — **ห้ามอยู่ใน git/แชต/หน้าจอ**
   * ใส่ลง [`templates/unlock_script.js`](skills/remote-phone-control/templates/unlock_script.js)
     ที่ตัวแปร `SEQ = "YOUR_PATTERN"` (เลข 7 หลักตามลำดับที่นิ้วผ่าน  keypad: 1=บนซ้าย … 9=ล่างขวา)
   * **สอบเขียนจริงครั้งแรก**: เปิด pointer-location (`settings put system pointer_location 1`)
     ให้ผู้ใช้วาด pattern จริง 1 ครั้ง → ดึงหน้าจอมาหาจุดศูนย์กลางของจุดทั้ง 9
     (อัลกอริทึมเต็มอยู่ที่ [`references/grid-detect-and-draw.md`](skills/remote-phone-control/references/grid-detect-and-draw.md))
   * ⛔ **ห้ามเดาพิกัด** — ผิด 5 ครั้ง = โดนล็อก 30 วินาที
2. **IP เซิร์ฟเวอร์** — แทน `YOUR_VPS_PUBLIC_IP` ในทุกไฟล์
3. **WireGuard keys / PSK** — gen ใหม่ในเครื่องคุณ ห้าม commit
4. **อีเมลรับไฟล์** — แทน `you@example.com`

> คำสั่ง `locksettings` (ฝั่ง `android-remote-control`) สามารถอ่าน/ตั้งค่า pattern ผ่าน adb ได้โดยไม่ต้อง root
> — ให้อ่านค่าจาก vault เป็นไฟล์ชั่วคราว 0600 เท่านั้น และ **ห้าม echo ค่าออกมาทาง stdout/แชต**

---

## ⚠️ สิ่งที่ถูกปกปิด (Redaction)

| รายการ | แทนที่ด้วย | เหตุผล |
|---|---|---|
| Unlock pattern จริง (รูปทรง + เลข keypad + พิกัดเส้น) | `YOUR_PATTERN` | ความลับหลัก — เข้าถึงเครื่องได้ |
| IP สาธารณะของเซิร์ฟเวอร์ | `YOUR_VPS_PUBLIC_IP` | หลีกเลี่ยงการเปิดเป้าหมายโจมตี/DoS |
| อีเมลส่วนตัว | `you@example.com` | ข้อมูลส่วนบุคคล |
| พาธผู้ใช้ `/home/<user>` | `~` / `$HOME` | portability + ไม่เปิดชื่อผู้ใช้ |
| WireGuard private key / PSK | ไม่มีใน repo (gen ใหม่) | credential |

ตรวจซ้ำด้วยการ grep ทั้ง repo ก่อนทุกครั้งที่ push:
pattern digits, `-----BEGIN`, IP เซิร์ฟจริง, `@gmail`, `password=`, token

---

## 🧩 ติดตั้งเป็นสกิล Hermes

```bash
git clone https://github.com/<owner>/<repo>.git
cp -r <repo>/skills/remote-phone-control   ~/.hermes/skills/devops/     # หรือ ~/.hermes/skills/
cp -r <repo>/skills/android-remote-control ~/.hermes/skills/
```

Hermes จะอ่าน `SKILL.md` (name/description/tags) แล้วเรียกใช้อัตโนมัติเมื่อผู้ใช้สั่งงานโทรศัพท์
(เช่น "ปลดล็อกให้หน่อย", "ดูหน้าจอมือถือ", "ปิดการแจ้งเตือน shopee")

---

## 🔥 Pitfalls ที่เจอบ่อย (สรุป)

1. พอร์ต adb **หมุนทุกครั้ง** ที่ wireless-debug re-init / รีบูต → สแกนใหม่เสมอ ห้ามใช้พอร์ตเก่า
2. รหัสจับคู่หมดอายุใน ~2 นาที (`Wrong password or connection was dropped` = ขอใหม่)
3. จอปิด ≠ เครื่องหลับ — เช็ค `dumpsys display | grep mScreenState` เสมอ (อย่าดูแค่ `mWakefulness`)
4. หน้าจอปิด → `screencap` คืน PNG ดำขนาดคงที่ (~15 KB) หรือ 0 ไบต์ — ภาพจริง `>100KB`
5. ห้ามสร้าง flow ด้วย `input tap/swipe` บน MIUI — บล็อกแบบ flapping → ใช้ **AutoJS6 `gesture()`**
6. `logcat -c` ก่อนยิงสคริปต์ทุกครั้ง แล้วอ่านเฉพาะ `GlobalConsole` + marker `HOUSTON`
7. บน MIUI keyguard **ไม่อยู่ใน accessibility tree** → อ่านค่าจุดไม่ได้ ต้องใช้เส้นที่สอบไว้แล้ว
8. MIUI ฆ่า WireGuard ตอนจอปิด (PowerKeeper `AutoLockOffClean`) → ตั้ง "ไม่มีข้อจำกัด" + ปิด
   "ล้างแคชเมื่อล็อกเครื่อง" + Always-on VPN — **Background process limit ไม่ช่วย**
9. Recents บน MIUI: ปัดการ์ดทีละใบแบบแนวนอน — กด "ล้างทั้งหมด" = WireGuardตายตาม
10. host `uiautomator dump` กับ AutoJS6 แย่ง accessibility service ตัวเดียวกัน → ใช้ตัวใดตัวหนึ่งในแต่ละ phase

> รายละเอียดครบถ้วนอยู่ใน `SKILL.md` → หัวข้อ **Pitfalls** (ทุกข้ออิงหลักฐานจริงจากเครื่องทดสอบ)

---

## 📄 License

MIT — ดู [LICENSE](LICENSE)

**คำเตือน**: ใช้กับอุปกรณ์ที่ **คุณเป็นเจ้าของและอนุญาตเท่านั้น**
การปลดล็อก/ควบคุมอุปกรณ์ของผู้อื่นโดยไม่ได้รับอนุญาตเป็นเรื่องผิดกฎหมาย
