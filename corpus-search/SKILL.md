---
name: corpus-search
description: >
  ค้นเอกสารกองใหญ่ในเครื่อง (เล่มมาตรฐาน, คลังความรู้, wiki/Obsidian vault, ไฟล์ .txt/.md)
  แล้วคืนเฉพาะ excerpt สั้น ๆ พร้อมชื่อไฟล์+เลขบรรทัดสำหรับอ้างอิง — แทนการอ่านทั้งเล่ม
  เข้า context ซึ่งเปลือง token มหาศาล
  Use this skill BEFORE answering any question whose answer should come from local documents:
  standards books (มสพร./มรด./TGIX), a knowledge base, a wiki, a corpus folder, or any
  collection of .txt/.md files — especially when the user asks "เล่มเราเขียนว่าอย่างไร",
  "มีนิยามคำนี้ไหม", "อ้างอิงจากเล่มไหน", or asks you to cite sources.
  Also use it before drafting or reviewing a document that must be consistent with existing
  standards, and whenever you are tempted to read a large file into context to find one fact.
  Do NOT use for searching code (use Grep/Glob) or for questions the local documents cannot answer.
compatibility: >
  python3 อย่างเดียว — ไม่ต้องลง dependency ใด ๆ ไม่ต้องใช้ vector DB / embedding / network
  ทำงานบนเครื่องล้วน (ข้อมูลไม่ออกนอกเครื่อง)
---

# Corpus Search

ค้นคลังเอกสารในเครื่อง คืนเฉพาะ excerpt ที่ตรงประเด็น พร้อมที่อยู่สำหรับอ้างอิง

## ทำไมต้องมี skill นี้

เอกสารมาตรฐานหนึ่งเล่มมักยาว 100,000+ ตัวอักษร คลังทั้งชุดอาจเป็นล้าน
ถ้าโยนเข้า context ทั้งหมดเพื่อตอบคำถามเดียว = ช้า แพง และ AI มักหลงประเด็น

skill นี้ค้นด้วยสคริปต์ (deterministic, ฟรี) แล้วคืนแค่ 5 ท่อน ๆ ละ ~600 ตัวอักษร
AI อ่านเฉพาะเท่านี้ก็ตอบพร้อมอ้างอิงได้ — **ประหยัด token ระดับ 100 เท่า**

## กฎเหล็ก: ค้นก่อนตอบ ห้ามตอบจากความจำ

เมื่อคำถามเกี่ยวกับเนื้อหาในเอกสารของผู้ใช้:

1. **ค้นก่อนเสมอ** — อย่าตอบจากความรู้ทั่วไปของโมเดล เพราะจะได้ชื่อ attribute/นิยามที่
   "ฟังดูถูก" แต่ไม่ตรงกับเล่มจริง (เคยเกิดจริง: AI ตอบ `cd:PersonIdentifier` ทั้งที่เล่มเขียนว่า `cd:PersonID`)
2. **อ้างอิงเฉพาะสิ่งที่ผลค้นแสดงจริง** — ถ้าผลค้นไม่มี ให้บอกว่าไม่พบ อย่าเดา
3. **ถ้าค้นไม่เจอ ให้ลองคำอื่นอีก 2-3 คำก่อนสรุป** — นี่คือ keyword search ไม่ใช่ semantic
   คำพ้องความหมายจะไม่แมตช์ (ค้น "เอกสารรับรอง" ไม่เจอ ลอง "VC", "credential", "ใบรับรอง")

## Workflow

### 1. ดูก่อนว่าในคลังมีอะไร

```bash
python3 scripts/corpus_search.py --list --corpus-dir ./corpus
```
```
corpus: ./corpus  (6 ไฟล์)
  tgix-semantic-vc-vp-standard-v0.20.txt  (184,888 ตัวอักษร)
  ...
```
ถ้าคลังว่าง/ไม่มีโฟลเดอร์ → ต้องนำเอกสารเข้าก่อน (PDF ให้ใช้ skill **`thai-pdf-extract`**)

### 2. ค้น

```bash
# ค้นพื้นฐาน (ค้นใน ./corpus, คืน 5 อันดับ)
python3 scripts/corpus_search.py "selective disclosure"

# ระบุคลังเอง + เอาเยอะขึ้น
python3 scripts/corpus_search.py "เอกสารรับรองดิจิทัล" -k 8 --corpus-dir ~/vault

# จำกัดเฉพาะบางเล่ม (กรองจากชื่อไฟล์)
python3 scripts/corpus_search.py "cd:PersonID" --scope person

# ผลลัพธ์เป็น JSON (เอาไปประมวลผลต่อ)
python3 scripts/corpus_search.py "unlinkability" --json
```

ผลลัพธ์แต่ละรายการ: `ชื่อไฟล์:เลขบรรทัด (score N)` + ข้อความ ~600 ตัวอักษร

### 3. อ่านเพิ่มเฉพาะจุดที่ต้องการ

ถ้า excerpt ไม่พอ ให้ใช้เลขบรรทัดที่ได้ ไปอ่านเฉพาะช่วงนั้นด้วย Read tool
(`offset` = เลขบรรทัด, `limit` = 50-100 บรรทัด) — **อย่าอ่านทั้งไฟล์**

### 4. ตอบพร้อมอ้างอิง

รูปแบบที่ควรใช้:
> ตามเล่ม `tgix-semantic-vc-vp-dd-p4-v15.txt` (บรรทัด 1719) ระบุว่า ...

## ตัวเลือกเพิ่มเติม

| ตัวเลือก | ทำอะไร | ใช้เมื่อไหร่ |
|---|---|---|
| `-k N` | จำนวนผลลัพธ์ (default 5) | อยากได้ภาพกว้างขึ้น |
| `--scope <คำ>` | เฉพาะไฟล์ที่ชื่อมีคำนี้ | รู้อยู่แล้วว่าอยู่เล่มไหน |
| `--corpus-dir <path>` | ระบุคลัง (หรือตั้ง env `CORPUS_DIR`) | คลังไม่ได้อยู่ที่ `./corpus` |
| `--chars N` | ความยาว excerpt (default 600) | อยากได้บริบทยาวขึ้น/สั้นลง |
| `--window N` | ขนาดหน้าต่างค้น (default 1200) | เอกสารย่อหน้ายาวมาก |
| `--json` | ผลลัพธ์เป็น JSON | เอาไปประมวลผลต่อ |

## วิธีทำงานภายใน (เผื่อต้องปรับ)

Keyword window search — ไม่ใช้ vector DB:
1. ซอยแต่ละไฟล์เป็นหน้าต่างซ้อนกัน (1,200 ตัวอักษร ซ้อน 200 — กันคำตอบขาดตรงรอยต่อ)
2. ให้คะแนน: เจอทั้งวลี = 3 คะแนน/ครั้ง, เจอคำเดี่ยว = 1 คะแนน/ครั้ง
3. คืนหน้าต่างคะแนนสูงสุด k อันดับ

เลือกวิธีนี้เพราะคลังขนาดไม่กี่สิบเล่ม ค้นเร็วพอ ไม่ต้องลง dependency ไม่ต้อง index ใหม่
เมื่อเอกสารเปลี่ยน และไม่ต้องส่งข้อมูลออกนอกเครื่อง (สำคัญกับเอกสารราชการที่ยังเป็นร่าง)

## ข้อจำกัดที่ต้องบอกผู้ใช้ตามตรง

- **เป็น keyword search ไม่ใช่ semantic** — คำพ้อง/ความหมายใกล้เคียงค้นไม่เจอ
  ถ้าค้นไม่เจอ **อย่าเพิ่งสรุปว่า "ไม่มีในเล่ม"** ให้ลองคำอื่นก่อน แล้วค่อยรายงานว่าค้นด้วยคำใดบ้าง
- **อ่านเฉพาะ `.txt` และ `.md`** — PDF/Word ต้องแปลงเข้าคลังก่อน (`thai-pdf-extract` สำหรับ PDF)
- **ไม่รู้บริบทข้ามไฟล์** — ถ้าคำตอบต้องประกอบจากหลายเล่ม ต้องค้นหลายรอบแล้วสังเคราะห์เอง
