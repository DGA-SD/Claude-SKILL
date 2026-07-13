#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_pdf — แปลง PDF ภาษาไทย → text สะอาด ด้วย pdftotext -layout (poppler)

แก้ปัญหาที่ตัวแปลงทั่วไป (markitdown / PyPDF ฯลฯ) ทำภาษาไทยเพี้ยน:
สระบน-ล่างและวรรณยุกต์หลุดออกจากพยัญชนะ หรือแตกบรรทัด

ใช้:
    python3 extract_pdf.py <file.pdf> [<file2.pdf> ...] [-o OUTDIR] [--stdout]
    python3 extract_pdf.py --check          # ตรวจว่าเครื่องมีเครื่องมือครบไหม

ผลลัพธ์: <OUTDIR>/<ชื่อไฟล์>.txt   (default OUTDIR = ./corpus)
รายงานคุณภาพต่อไฟล์: จำนวนบรรทัด, % บรรทัดสั้น, สัดส่วนอักขระไทย
ถ้าได้ text น้อยผิดปกติ = PDF น่าจะเป็นภาพสแกน → ต้อง OCR ก่อน (สคริปต์จะเตือน)
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys

THAI_RANGE = re.compile(r"[฀-๿]")
MIN_CHARS_PER_PAGE = 80  # ต่ำกว่านี้ต่อหน้า = น่าจะเป็น PDF สแกน (ไม่มี text layer)

# PDF ราชการบางไฟล์ (ฟอนต์บางตัว) เข้ารหัสสระอา (า) เป็นสระอำ (ำ)
# ทำให้ได้คำที่ไม่มีอยู่จริงในภาษาไทย เช่น "กำร" แทน "การ"
# รายการนี้เลือกเฉพาะคำที่ "ไม่ใช่คำไทยที่ถูกต้อง" เท่านั้น จึงแทนที่ได้ปลอดภัย
# (ห้าม replace ำ→า ทั้งไฟล์ เพราะจะพังคำที่ถูกต้อง เช่น คำ ทำ นำ สำนัก กำหนด)
SARA_AM_FIXES = {
    "กำร": "การ",
    "ควำม": "ความ",
    "สำมำรถ": "สามารถ",
    "มำตรฐำน": "มาตรฐาน",
    "อย่ำง": "อย่าง",
    "ผ่ำน": "ผ่าน",
    "ต่ำง": "ต่าง",
    "ข้ำง": "ข้าง",
    "หมำย": "หมาย",
    "รำย": "ราย",
    "งำน": "งาน",
    "ฐำน": "ฐาน",
    "บำง": "บาง",
    "ระหว่ำง": "ระหว่าง",
}


def have_pdftotext() -> bool:
    return shutil.which("pdftotext") is not None


def page_count(pdf_path: str) -> int | None:
    """นับหน้าจาก pdfinfo ถ้ามี — ใช้ประเมินว่า text ที่ได้น้อยผิดปกติไหม"""
    if shutil.which("pdfinfo") is None:
        return None
    try:
        out = subprocess.run(
            ["pdfinfo", pdf_path], capture_output=True, text=True, check=True
        ).stdout
        m = re.search(r"^Pages:\s+(\d+)", out, re.M)
        return int(m.group(1)) if m else None
    except subprocess.CalledProcessError:
        return None


def clean(txt: str) -> str:
    txt = txt.replace("\r\n", "\n").replace("\r", "\n")
    txt = re.sub(r"[ \t]+\n", "\n", txt)      # ตัด trailing space
    txt = re.sub(r"\n{3,}", "\n\n", txt)      # ยุบบรรทัดว่างเกิน 2
    return txt.strip() + "\n"


def count_sara_am_corruption(txt: str) -> int:
    """นับคำที่เพี้ยนจากปัญหา font encoding (สระอา -> สระอำ)"""
    return sum(txt.count(bad) for bad in SARA_AM_FIXES)


def fix_sara_am(txt: str) -> tuple[str, int]:
    """ซ่อมคำที่เพี้ยนแบบเจาะจงคำ (ไม่แตะ ำ ในคำที่ถูกต้อง)"""
    fixed = 0
    for bad, good in SARA_AM_FIXES.items():
        n = txt.count(bad)
        if n:
            txt = txt.replace(bad, good)
            fixed += n
    return txt, fixed


def quality(txt: str, pages: int | None) -> dict:
    lines = txt.splitlines()
    n = len(lines)
    short = sum(1 for l in lines if len(l.strip()) < 15)
    thai = len(THAI_RANGE.findall(txt))
    chars = len(txt)
    q = {
        "lines": n,
        "chars": chars,
        "short_pct": round(short * 100 / max(n, 1)),
        "thai_pct": round(thai * 100 / max(chars, 1)),
        "pages": pages,
        "warn": [],
    }
    if pages and chars < pages * MIN_CHARS_PER_PAGE:
        q["warn"].append(
            f"ได้ text น้อยมาก ({chars} ตัวอักษร / {pages} หน้า) — "
            "PDF นี้น่าจะเป็นภาพสแกน ไม่มี text layer ต้อง OCR ก่อน (เช่น ocrmypdf)"
        )
    elif chars < 200:
        q["warn"].append("ได้ text แทบไม่มีเลย — PDF อาจเป็นภาพสแกน หรือไฟล์เสีย")
    if q["short_pct"] > 70 and n > 20:
        q["warn"].append(
            f"บรรทัดสั้นผิดปกติ ({q['short_pct']}%) — layout อาจเป็นคอลัมน์/ตารางซับซ้อน "
            "ตรวจไฟล์ผลลัพธ์ด้วยตาก่อนใช้งาน"
        )
    bad = count_sara_am_corruption(txt)
    if bad:
        q["sara_am"] = bad
        q["warn"].append(
            f"พบคำเพี้ยนจาก font encoding {bad} จุด (สระอา->สระอำ เช่น 'กำร' แทน 'การ') "
            "— รันซ้ำด้วย --fix-sara เพื่อซ่อมอัตโนมัติ"
        )
    return q


def extract(
    pdf_path: str, outdir: str, to_stdout: bool = False, fix_sara: bool = False
) -> int:
    if not os.path.isfile(pdf_path):
        print(f"!! ไม่พบไฟล์: {pdf_path}", file=sys.stderr)
        return 1

    pages = page_count(pdf_path)
    proc = subprocess.run(
        ["pdftotext", "-layout", "-enc", "UTF-8", pdf_path, "-"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(f"!! pdftotext ล้มเหลว: {pdf_path}\n{proc.stderr.strip()}", file=sys.stderr)
        return 1

    txt = clean(proc.stdout)
    fixed = 0
    if fix_sara:
        txt, fixed = fix_sara_am(txt)
    q = quality(txt, pages)
    if fixed:
        print(f"   ✔ ซ่อมคำเพี้ยนจาก font encoding {fixed} จุด (สระอำ -> สระอา)")

    if to_stdout:
        sys.stdout.write(txt)
    else:
        os.makedirs(outdir, exist_ok=True)
        out = os.path.join(
            outdir, os.path.splitext(os.path.basename(pdf_path))[0] + ".txt"
        )
        with open(out, "w", encoding="utf-8") as f:
            f.write(txt)
        pg = f", pages={q['pages']}" if q["pages"] else ""
        print(
            f"-> {out}  (lines={q['lines']}, chars={q['chars']}{pg}, "
            f"short={q['short_pct']}%, thai={q['thai_pct']}%)"
        )

    for w in q["warn"]:
        print(f"   ⚠️  {w}", file=sys.stderr)
    return 2 if q["warn"] else 0


def main() -> int:
    p = argparse.ArgumentParser(
        description="แปลง PDF ภาษาไทยเป็น text สะอาด (pdftotext -layout)"
    )
    p.add_argument("pdfs", nargs="*", help="ไฟล์ PDF ที่จะแปลง")
    p.add_argument(
        "-o", "--outdir", default="./corpus",
        help="โฟลเดอร์ผลลัพธ์ (default: ./corpus)",
    )
    p.add_argument(
        "--stdout", action="store_true",
        help="พิมพ์ text ออก stdout แทนการเขียนไฟล์ (ใช้กับไฟล์เดียว)",
    )
    p.add_argument(
        "--fix-sara", action="store_true",
        help="ซ่อมคำเพี้ยนจาก font encoding (สระอำ->สระอา) แบบเจาะจงคำที่ไม่ใช่คำไทย",
    )
    p.add_argument(
        "--check", action="store_true", help="ตรวจว่าเครื่องมี pdftotext (poppler) ไหม"
    )
    a = p.parse_args()

    if a.check:
        ok = have_pdftotext()
        print("pdftotext:", shutil.which("pdftotext") if ok else "NOT FOUND")
        print("pdfinfo  :", shutil.which("pdfinfo") or "NOT FOUND (optional)")
        if not ok:
            print(
                "\nติดตั้ง poppler ก่อน:\n"
                "  macOS : brew install poppler\n"
                "  Ubuntu: sudo apt install poppler-utils",
                file=sys.stderr,
            )
            return 1
        return 0

    if not have_pdftotext():
        print(
            "!! ไม่พบคำสั่ง pdftotext (poppler)\n"
            "   macOS : brew install poppler\n"
            "   Ubuntu: sudo apt install poppler-utils",
            file=sys.stderr,
        )
        return 1

    if not a.pdfs:
        p.print_usage()
        return 1

    rc = 0
    for pdf in a.pdfs:
        rc = max(rc, extract(pdf, a.outdir, a.stdout, a.fix_sara))
    return rc


if __name__ == "__main__":
    sys.exit(main())
