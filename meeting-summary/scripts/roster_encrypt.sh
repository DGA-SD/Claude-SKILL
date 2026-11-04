#!/usr/bin/env bash
# เข้ารหัสไฟล์รายชื่อ (references/dga-people.md) เป็น .enc แล้วให้ผู้ใช้ลบต้นฉบับ plaintext เอง
# กุญแจหาตามลำดับเดียวกับ roster_decrypt.sh (env MEETING_ROSTER_KEY > macOS Keychain > ~/.config/meeting-summary/roster.key)
# ครั้งแรกยังไม่มีกุญแจ: สร้างและเก็บให้ด้วย --init  (Mac = Keychain · OS อื่น = ไฟล์ roster.key chmod 600)
# ใช้:  bash roster_encrypt.sh --init            สร้างกุญแจใหม่ (ทำครั้งเดียวต่อเครื่อง)
#       bash roster_encrypt.sh <ไฟล์.md>          ได้ <ไฟล์.md>.enc (chmod 600)
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"

if [ "${1:-}" = "--init" ]; then
  newkey="$(openssl rand -base64 32)"
  if command -v security >/dev/null 2>&1; then
    security add-generic-password -a "$USER" -s meeting-roster -w "$newkey" -U >/dev/null
    echo "เก็บกุญแจใหม่ใน macOS Keychain (service: meeting-roster) แล้ว"
  else
    mkdir -p "$HOME/.config/meeting-summary"
    umask 077; printf '%s\n' "$newkey" > "$HOME/.config/meeting-summary/roster.key"
    echo "เก็บกุญแจใหม่ที่ $HOME/.config/meeting-summary/roster.key (สิทธิ์ 600) แล้ว"
  fi
  echo "เครื่องอื่นที่ต้องอ่านไฟล์เดียวกัน: ส่งกุญแจผ่านช่องทางลับแล้วเก็บด้วยวิธีเดียวกัน (ห้ามส่งพร้อมไฟล์ .enc)"
  exit 0
fi

f="${1:?ระบุไฟล์รายชื่อ .md ที่จะเข้ารหัส (หรือ --init)}"
key="${MEETING_ROSTER_KEY:-}"
if [ -z "$key" ] && command -v security >/dev/null 2>&1; then
  key="$(security find-generic-password -s meeting-roster -w 2>/dev/null || true)"
fi
if [ -z "$key" ] && [ -f "$HOME/.config/meeting-summary/roster.key" ]; then
  key="$(tr -d '\r\n' < "$HOME/.config/meeting-summary/roster.key")"
fi
[ -n "$key" ] || { echo "ยังไม่มีกุญแจ: รัน bash $0 --init ก่อน" >&2; exit 3; }

MEETING_ROSTER_KEY="$key" openssl enc -aes-256-cbc -pbkdf2 -pass env:MEETING_ROSTER_KEY -in "$f" -out "$f.enc"
chmod 600 "$f.enc"
echo "เข้ารหัสแล้ว: $f.enc"
echo "ตรวจก่อนลบต้นฉบับ: bash $here/roster_decrypt.sh \"$f.enc\" | diff - \"$f\" && echo ตรงกัน"
echo "แล้วลบ plaintext: rm \"$f\"  (รวมไฟล์ .bak ถ้ามี)"
