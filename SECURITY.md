# Security Policy / นโยบายความปลอดภัย

## What this repository must NEVER contain

| ห้ามเด็ดขาด | ตัวอย่าง |
|---|---|
| Unlock pattern / PIN / password จริง | เลข keypad 7 หลัก, `SEQ = "..."` ของเครื่องจริง |
| Private keys | WireGuard `PrivateKey` / `PresharedKey`, SSH keys, `-----BEGIN ...` |
| Token / session / API key | `ghp_...`, cookie, bearer token |
| IP สาธารณะของเซิร์ฟเวอร์จริง / อีเมลส่วนตัว | แทนด้วย `YOUR_VPS_PUBLIC_IP`, `you@example.com` |
| เนื้อหาส่วนบุคคลจากหน้าจอมือถือ | ข้อความแชต, ภาพหน้าจอจริง, รายชื่อผู้ติดต่อ |

สคริปต์ใน repo อ่านความลับจาก **vault ภายนอก** (เช่น `~/.hermes/data/vault.json`) หรือไฟล์ `0600`
ที่ผู้ใช้สร้างเองในเครื่องของตัวเอง — ไม่มีค่าจริงฝังในโค้ด

## Pre-push checklist (ทำทุกครั้ง)

```bash
# รันจาก root ของ repo — ต้องได้ผลลัพธ์ว่างทั้งหมด
grep -rInE '7-4-1-5-3-6-9|[0-9]{7}|-----BEGIN|ghp_[A-Za-z0-9]|@gmail\.com|password\s*=\s*[^< ]' . \
  --exclude=LICENSE --exclude-dir=.git
```

ถ้าเจอค่าจริง → แทนด้วย placeholder (`YOUR_PATTERN`, `YOUR_VPS_PUBLIC_IP`, `you@example.com`)
แล้ว **แก้ใน git history ด้วย** (ยังไม่ commit = ลบทิ้งแล้ว commit ใหม่)

## Reporting

พบความลับหลุดใน repo นี้ → แจ้งเป็น GitHub Issue ทันที พร้อมลิงก์ไฟล์/commit
(อย่าแปะค่าจริงของความลับลงใน issue) แล้วให้เจ้าของ repo revoke/rotate ค่านั้นทันที
