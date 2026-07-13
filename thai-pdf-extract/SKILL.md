---
name: thai-pdf-extract
description: >
  แปลง PDF ภาษาไทย (โดยเฉพาะเอกสารราชการ/เล่มมาตรฐาน) ให้เป็นไฟล์ text สะอาด
  โดยสระและวรรณยุกต์ไม่เพี้ยน ไม่แตกบรรทัด — ใช้ pdftotext -layout (poppler)
  แทนตัวแปลงทั่วไป (markitdown / PyPDF / pdfplumber) ที่ทำภาษาไทยพัง
  Use this skill whenever the user asks to read, extract, convert, ingest, or summarize
  a PDF that contains Thai text — including Thai government documents (มสพร./มรด./ประกาศ),
  standards drafts, meeting documents, or any PDF being ingested into a knowledge base,
  wiki, Obsidian vault, or corpus for later search.
  Also use it when a previous PDF extraction produced garbled Thai (สระลอย, วรรณยุกต์หลุด,
  คำอย่าง "กำร" แทน "การ") — this skill detects and repairs that font-encoding corruption.
  Do NOT use for PDFs with no Thai text (a plain English PDF needs no special handling).
compatibility: >
  ต้องมี poppler (คำสั่ง pdftotext) และ python3
  macOS: brew install poppler | Ubuntu/Debian: sudo apt install poppler-utils
  ตรวจด้วย: python3 scripts/extract_pdf.py --check
---

# Thai PDF Extract

แปลง PDF ภาษาไทย → text สะอาด พร้อมรายงานคุณภาพ และตรวจจับ/ซ่อมปัญหา encoding

## ทำไมต้องมี skill นี้

ตัวแปลง PDF ทั่วไปที่ AI มักหยิบมาใช้ (markitdown, PyPDF2, pdfplumber) **ทำภาษาไทยเพี้ยน**:
สระบน-ล่างและวรรณยุกต์หลุดจากพยัญชนะ หรือแตกไปคนละบรรทัด ทำให้ข้อความที่ได้ค้นไม่เจอ
อ่านไม่รู้เรื่อง และถ้าเอาไปให้ AI อ่านต่อจะได้คำตอบที่ผิด

`pdftotext -layout` (จาก poppler) จัดการภาษาไทยได้ถูกต้องและรักษา layout เดิมไว้ด้วย
skill นี้ห่อมันไว้พร้อมการตรวจสอบคุณภาพที่จำเป็น

## Workflow

### 1. ตรวจเครื่องมือก่อน (ครั้งแรก / เครื่องใหม่)

```bash
python3 scripts/extract_pdf.py --check
```
ถ้าไม่พบ `pdftotext` ให้แจ้งผู้ใช้ติดตั้ง poppler ก่อน — **อย่า fallback ไปใช้ตัวแปลงอื่นเงียบ ๆ**
เพราะจะได้ภาษาไทยเพี้ยน ซึ่งเป็นปัญหาที่ skill นี้มีไว้แก้

### 2. แปลงไฟล์

```bash
# ไฟล์เดียว → ./corpus/<ชื่อไฟล์>.txt
python3 scripts/extract_pdf.py "เอกสาร.pdf"

# หลายไฟล์ + เลือกโฟลเดอร์ปลายทาง
python3 scripts/extract_pdf.py a.pdf b.pdf -o ~/vault/raw

# ไม่เขียนไฟล์ ขอดู text เลย (ไฟล์เดียว)
python3 scripts/extract_pdf.py "เอกสาร.pdf" --stdout
```

### 3. อ่านรายงานคุณภาพ — **ห้ามข้าม**

ทุกครั้งสคริปต์จะรายงานแบบนี้:
```
-> ./corpus/เอกสาร.txt  (lines=2695, chars=184886, pages=83, short=22%, thai=42%)
```

ตีความ:

| ค่า | ปกติ | ถ้าผิดปกติแปลว่า |
|---|---|---|
| `chars` เทียบกับ `pages` | > 80 ตัวอักษร/หน้า | **PDF เป็นภาพสแกน ไม่มี text layer** → ต้อง OCR ก่อน (เช่น `ocrmypdf`) สคริปต์จะเตือนให้ |
| `short%` | < 70% | layout ซับซ้อน (คอลัมน์/ตารางเยอะ) — ต้องเปิดไฟล์ดูด้วยตาก่อนเชื่อ |
| `thai%` | ตรงกับที่คาดของเอกสาร | ถ้าเป็น 0% ทั้งที่เอกสารเป็นภาษาไทย = สกัดผิดพลาด |

### 4. ถ้าเจอคำเตือนเรื่อง font encoding → ซ่อม

PDF ราชการบางไฟล์ (ฟอนต์บางตัว) เข้ารหัส **สระอา (า) เป็นสระอำ (ำ)** ทำให้ได้คำที่
ไม่มีอยู่จริงในภาษาไทย เช่น `กำร` แทน `การ`, `ควำม` แทน `ความ`, `สำมำรถ` แทน `สามารถ`

สคริปต์ตรวจจับให้อัตโนมัติ ถ้าเจอจะเตือน แล้วให้รันซ้ำด้วย:
```bash
python3 scripts/extract_pdf.py "เอกสาร.pdf" --fix-sara
```

การซ่อมเป็นแบบ **เจาะจงคำ** (แทนที่เฉพาะคำที่พิสูจน์ได้ว่าไม่ใช่คำไทยที่ถูกต้อง)
**ไม่ใช่** การ replace `ำ`→`า` ทั้งไฟล์ — เพราะจะทำลายคำที่ถูกต้องอย่าง คำ ทำ นำ สำนัก กำหนด สำคัญ

### 5. ตรวจงานด้วยตาก่อนใช้ต่อ (สำคัญ)

เปิดไฟล์ผลลัพธ์อ่านสัก 20-30 บรรทัด ยืนยันว่า:
- สระ/วรรณยุกต์อยู่กับพยัญชนะถูกต้อง (เช่น "สำนักงานพัฒนารัฐบาลดิจิทัล" ไม่ใช่ "สานักงานพัฒนารัฐบาลดิจิทัล")
- หัวข้อ/ตารางยังพอเดาโครงสร้างได้
- ไม่มีหน้าที่หายไปเป็นก้อน

## ข้อจำกัดที่ต้องบอกผู้ใช้ตามตรง

- **PDF สแกน (ภาพ) แปลงไม่ได้** — จะได้ไฟล์ว่างหรือแทบว่าง สคริปต์เตือนให้ แต่แก้ให้ไม่ได้
  ต้อง OCR ก่อน (`ocrmypdf --language tha input.pdf output.pdf` แล้วค่อยแปลง)
- **ตารางซับซ้อนจะเพี้ยนเรื่อง layout** — `-layout` รักษาตำแหน่งด้วยการเว้นวรรค
  ข้อมูลไม่หาย แต่โครงสร้างตารางต้องอ่านเอาความ ไม่ใช่ parse แบบ machine-readable
- **ไม่ได้รูปภาพ** — ได้เฉพาะ text

## ต่อยอด

ถ้าจุดหมายคือ "เอาเอกสารเข้าคลังไว้ให้ AI ค้นทีหลัง" ให้ใช้คู่กับ skill **`corpus-search`**:
แปลงด้วย skill นี้ลง `corpus/` แล้วค้นด้วย `corpus_search.py` ซึ่งคืนเฉพาะ excerpt สั้น ๆ
แทนที่จะโหลดเอกสารทั้งเล่มเข้า context (ประหยัด token มาก)
