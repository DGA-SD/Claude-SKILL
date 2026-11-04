#!/usr/bin/env bash
# ถอดรหัสไฟล์รายชื่อ (references/dga-people.md.enc) ออกทาง stdout เท่านั้น ไม่เขียน plaintext ลงดิสก์
# หลัก "กุญแจแยกกล่อง": กล่อง = ไฟล์ .enc ในโฟลเดอร์ skill · กุญแจ = หาตามลำดับนี้ (ตัวแรกที่เจอชนะ)
#   1. ตัวแปรแวดล้อม MEETING_ROSTER_KEY          (ทุก OS · Windows ตั้งใน User environment variables ได้)
#   2. macOS Keychain service "meeting-roster"     (เฉพาะ Mac · ไม่มีไฟล์กุญแจบนดิสก์)
#   3. ไฟล์ ~/.config/meeting-summary/roster.key    (ทุก OS · Windows = %USERPROFILE%\.config\meeting-summary\roster.key · chmod 600)
# ใช้:  bash roster_decrypt.sh [ไฟล์.enc]   (ค่าปริยาย = references/dga-people.md.enc ข้าง ๆ สคริปต์นี้)
# ต้องมี openssl (Mac/Linux มีในตัว · Windows มากับ Git for Windows)
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
f="${1:-$here/../references/dga-people.md.enc}"
[ -f "$f" ] || { echo "ไม่พบไฟล์เข้ารหัส: $f" >&2; exit 2; }

key="${MEETING_ROSTER_KEY:-}"
if [ -z "$key" ] && command -v security >/dev/null 2>&1; then
  key="$(security find-generic-password -s meeting-roster -w 2>/dev/null || true)"
fi
if [ -z "$key" ] && [ -f "$HOME/.config/meeting-summary/roster.key" ]; then
  key="$(tr -d '\r\n' < "$HOME/.config/meeting-summary/roster.key")"
fi
[ -n "$key" ] || { echo "ไม่พบกุญแจ: ตั้ง MEETING_ROSTER_KEY หรือเก็บใน Keychain (meeting-roster) หรือไฟล์ ~/.config/meeting-summary/roster.key" >&2; exit 3; }

MEETING_ROSTER_KEY="$key" openssl enc -d -aes-256-cbc -pbkdf2 -pass env:MEETING_ROSTER_KEY -in "$f"
