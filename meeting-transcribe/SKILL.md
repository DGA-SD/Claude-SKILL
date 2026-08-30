---
name: meeting-transcribe
description: >
  ถอดเสียงประชุมภาษาไทย (.m4a/.mp3/.wav และทุกฟอร์แมตที่ ffmpeg อ่านได้) เป็น
  transcript พร้อม timestamp ในเครื่องด้วย Typhoon ASR (scb10x/typhoon-asr-realtime)
  รองรับไฟล์ยาวระดับชั่วโมงโดยหั่นท่อนตามช่วงเงียบ มีโหมดแยกผู้พูด (--speakers,
  pyannote diarization) และโหมดใส่ชื่อจริงแทน speakerN โดยวิเคราะห์บริบทใน
  transcript ประกบรายชื่อผู้เข้าประชุม ข้อมูลเสียงไม่ออกจากเครื่อง
  Use this skill whenever the user provides a Thai meeting audio file and asks to
  transcribe it (ถอดเสียง / ถอดความ / transcribe), with or without speaker
  separation (แยกผู้พูด) or speaker naming (ใส่ชื่อผู้พูด / ใส่ชื่อ / map ชื่อ).
  Also use the naming workflow (section 4) when the user already has a
  .speakers.transcript.txt and asks to replace speakerN with real names.
  Do NOT use for non-Thai audio (the model is Thai-only) and do NOT use for
  summarizing minutes (that is the meeting-summary skill, downstream of this one).
compatibility: >
  macOS Apple Silicon (ทดสอบบน MacBook Air M3 24GB) หรือ Linux, python 3.10-3.13,
  ffmpeg. ติดตั้งครั้งแรกด้วย scripts/setup.sh (ดาวน์โหลด dependency ราว 3GB และ
  โมเดล ~460MB ตอนรันครั้งแรก) โหมดแยกผู้พูดต้องมี Hugging Face token ที่ได้รับ
  สิทธิ์เข้าถึงโมเดล pyannote (gated) ส่วนโหมดถอดเสียงปกติไม่ต้องใช้ token
---

# Meeting Transcribe

ถอดเสียงประชุมภาษาไทยเป็นข้อความในเครื่องทั้งหมด (ไม่มีข้อมูลออกสู่ cloud) ด้วยโมเดล
`scb10x/typhoon-asr-realtime` (FastConformer-Transducer 114M, CC-BY-4.0) ซึ่งเป็น
โมเดลตระกูล NVIDIA NeMo จึงรันผ่าน Ollama / LM Studio / whisper.cpp ไม่ได้
ต้องรันผ่าน Python ตามที่ skill นี้จัดไว้ให้

## ทำไมไม่ใช้ CLI `typhoon-asr` ทางการตรง ๆ

CLI ทางการมีข้อจำกัด 4 ข้อที่ script ของ skill นี้แก้ให้:
1. ไม่รับ .m4a จริง (README ของเขาบอกว่ารับ แต่โค้ดเช็คแค่ .wav/.mp3/.flac/.ogg)
2. โยนไฟล์ทั้งไฟล์เข้าโมเดลทีเดียว ไฟล์ยาวเกินไม่กี่นาทีจะกินแรมจนค้าง
   (script นี้หั่นท่อนละ ~40 วินาที ตัดเฉพาะช่วงเงียบ คำไม่ขาดกลาง)
3. โหลดโมเดลใหม่ทุกครั้งที่เรียก (script นี้โหลดครั้งเดียวถอดรวดทุกไฟล์)
4. พิมพ์ผลเป็น raw object ของ NeMo แทนที่จะเป็นข้อความ

## 1. เช็คความพร้อมก่อนใช้ (ทุกครั้ง)

```bash
ls <skill>/.venv-asr/bin/python 2>/dev/null || ls ~/projects/claude/asr/.venv/bin/python 2>/dev/null
```
ถ้าไม่พบ venv ที่ตำแหน่งใดเลย ให้ขออนุญาตผู้ใช้รัน `scripts/setup.sh` ก่อน
(ใช้เวลาหลายนาที ดาวน์โหลดราว 3GB) script หลักหา venv เองตามลำดับ:
`$MEETING_ASR_PY` > `<skill>/.venv-asr` > `~/projects/claude/asr/.venv`
(ฝั่ง diarization ใช้ `$MEETING_DIAR_PY` > `<skill>/.venv-diar` > `~/projects/claude/asr/.venv-diar`)

## 2. ถอดเสียงแบบปกติ

```bash
python3 <skill>/scripts/transcribe.py meeting1.m4a meeting2.m4a --outdir out
```
ได้ `<ชื่อไฟล์>.transcript.txt` บรรทัดละท่อนพร้อม timestamp จริง:
```
[00:00:00] สวัสดีครับ วันนี้เป็นการประชุม...
[00:00:43] วาระแรกคือ...
```
ตัวเลือก: `--chunk วินาที` (ค่าเริ่มต้น 40), `--batch N` (4), `--outdir DIR`

ความเร็วที่วัดจริงบน MacBook Air M3 (CPU): เสียง 29 นาทีใช้ ~30 วินาที
(เร็วกว่าเวลาจริง ~60 เท่า) แรมสูงสุด ~3.3GB ควรรันเป็น background task
เมื่อไฟล์ยาวเกิน 30 นาที

## 3. โหมดแยกผู้พูด (--speakers)

```bash
python3 <skill>/scripts/transcribe.py meeting.m4a --speakers --num-speakers 10 --outdir out
```
ได้ `<ชื่อไฟล์>.speakers.transcript.txt`:
```
[00:01:12] speaker1: ขอเปิดประชุมนะครับ...
[00:01:45] speaker2: ขออนุญาตนำเสนอวาระแรกครับ...
```
หลักการ: pyannote (speaker-diarization-3.1) หาช่วงเวลาของผู้พูดแต่ละคนก่อน
แล้วส่งเสียงรายช่วงให้ Typhoon ถอด pyannote รันบน GPU ของ Mac (MPS) อัตโนมัติ

ที่วัดจริงบน M3: เสียง 1 ชม. 32 นาที ใช้ ~14 นาที แรมสูงสุด ~5.7GB
ใส่ `--num-speakers N` เมื่อรู้จำนวนผู้พูดจริง จะแม่นขึ้นชัดเจน

ข้อควรรู้ที่ต้องแจ้งผู้ใช้:
- จำนวน speaker ที่ตรวจพบมักสูงเกินจริง (เสียงคนเดียวกันถูกแยกเป็นหลาย cluster)
- ช่วงพูดซ้อนกันจะได้สองบรรทัด timestamp เดียวกัน เป็นเรื่องปกติ
- หมายเลข speaker เรียงตามการปรากฏครั้งแรก ถอดคนละไฟล์เลขไม่ตรงกัน

## 4. โหมดใส่ชื่อผู้พูด (งานวิเคราะห์ของ Claude ไม่ใช่ script)

เมื่อผู้ใช้ขอ "ใส่ชื่อ" ให้ทำกับไฟล์ `.speakers.transcript.txt` ดังนี้:

**Input ที่ควรขอ (ถ้ายังไม่ได้):** รายชื่อผู้เข้าประชุม เช่น attendance report จาก
Teams/Zoom (ถ้าเป็น PDF ภาษาไทยให้แปลงด้วย skill `thai-pdf-extract` ก่อน)
และจำนวนผู้พูดโดยประมาณ ถ้าไม่มีรายชื่อก็ทำได้แต่ความมั่นใจจะลดลง

**ขั้นตอน:**
1. อ่าน transcript ทั้งไฟล์ (ห้ามอ่านแค่บางส่วนแล้วสรุป)
2. เก็บหลักฐาน 4 ชนิด:
   - การแนะนำตัว ("ผมชื่อ X จากหน่วยงาน Y") ชัดสุด
   - การเชิญ ("ขอเชิญคุณ X") ผู้พูดถัดไปมักคือ X แต่ระวังเลขาแทรกก่อน
   - ช่วงขานชื่อสำรวจองค์ประชุม: คนที่ตอบรับหลังถูกขานชื่อคือคนนั้น (ขุมทรัพย์หลัก)
   - การขอบคุณหลังพูดจบ ("ขอบคุณท่าน X") ยืนยันย้อนหลังว่าใครเพิ่งพูด
3. ตรวจความบริสุทธิ์ของแต่ละ cluster ก่อน map เพราะ diarizer พลาด 2 แบบเสมอ:
   - over-split: เสียงคนเดียว (โดยเฉพาะประธานและเลขา) ถูกแยกเป็น 2-3 cluster
     ให้ map หลาย cluster เข้าชื่อเดียวได้
   - merge: เสียงลักษณะใกล้กัน (เช่นเสียงผู้หญิงผ่านออนไลน์หลายคน) ถูกรวมเป็น
     cluster เดียว และมักมี junk cluster หนึ่งที่ปนหลายเสียงจากไมค์ห้องประชุม
     cluster แบบนี้ต้องตัดสินรายบรรทัดจากบริบท ห้าม map ทั้ง cluster
4. สร้าง Python script ชั่วคราว (ใน scratchpad) ที่มี cluster_default map กับ
   line_override dict รายบรรทัด แล้ว generate ไฟล์ใหม่ ห้ามแก้ transcript ด้วยมือ
5. นโยบาย label:
   - มั่นใจสูง (ขานชื่อ/แนะนำตัว/ถูกขอบคุณระบุชื่อ): `ชื่อ (บทบาท)` เช่น `ดร.สมชาย (ประธาน)`
   - อนุมานจากบริบท: ติดท้าย `(บทบาท, คาดว่า)`
   - ตีความไม่ออกจริง ๆ: คงไว้เป็น speakerN เดิม ห้ามเดา
   - สะกดชื่อไทยจากเสียง + รายชื่อภาษาอังกฤษ ให้เขียนหมายเหตุเตือนเรื่องการสะกด
6. หัวไฟล์ผลลัพธ์ต้องมี header อธิบายวิธีอ่าน (ความหมายของ "คาดว่า", speakerN
   ที่เหลือ, คำเตือนการสะกดชื่อ) บันทึกเป็น `<ชื่อเดิม>.named.transcript.txt`
7. รายงานผู้ใช้เป็นตารางเทียบ speaker กับชื่อ พร้อมหลักฐานที่ใช้ตัดสินและระดับ
   ความมั่นใจรายคน และสถิติ (กี่บรรทัดระบุได้ / เหลือ speakerN กี่บรรทัด)

ผลที่วัดจริง: ประชุมกรรมการ 1.5 ชม. 17 diarized clusters ระบุชื่อได้ 95% ของ
บรรทัดทั้งหมด (386/405) และการ map ชื่อช่วยยุบ cluster ที่แยกเกินให้เหลือ
จำนวนคนจริงไปในตัว

**PDPA:** transcript และไฟล์ .named มีชื่อบุคคลจริง เก็บไว้ในเครื่องผู้ใช้เท่านั้น
ห้าม commit ขึ้น repo (มี .gitignore กันไว้แล้ว) และห้ามส่งออกนอกเครื่อง

## 5. Troubleshooting

| อาการ | สาเหตุ / ทางแก้ |
|---|---|
| `ERROR: ASR venv not found` | ยังไม่ได้รัน `scripts/setup.sh` |
| `torchaudio has no attribute AudioMetaData` | มีคนอัปเกรด torchaudio ใน .venv-diar ให้ลง `torch==2.8.* torchaudio==2.8.*` กลับ |
| `hf_hub_download() unexpected keyword use_auth_token` | huggingface_hub ถูกอัปเกรดเป็น 1.x ให้ลง `huggingface_hub<1.0` กลับ |
| `Weights only load failed` ตอน diarize | diarize.py ใน skill นี้แก้ให้แล้ว ถ้าเจอแปลว่าไปเรียก pyannote ตรงโดยไม่ผ่าน script |
| `Could not load pyannote/speaker-diarization-3.1` | ยังไม่มี HF token หรือยังไม่กดขอสิทธิ์ gated model ทั้ง 2 ตัว (ดูท้าย setup.sh) |
| ถอดออกมาว่าง/สั้นผิดปกติ | เช็คว่าเสียงเป็นภาษาไทยและไม่ใช่ไฟล์เงียบ ลองลด `--chunk` เหลือ 30 |

## 6. ใช้ต่อกับ skill อื่น

ผลลัพธ์ .transcript.txt / .named.transcript.txt ส่งเข้า skill `meeting-summary`
เพื่อทำรายงานสรุปการประชุม (.md + .docx) ได้ทันที โหมด have-quote จะได้ประโยชน์
จากชื่อผู้พูดจริงเป็นพิเศษ
