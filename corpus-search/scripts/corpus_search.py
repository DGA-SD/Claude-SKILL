#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
corpus_search — ค้นเอกสารกองใหญ่ แล้วคืนเฉพาะ excerpt สั้น ๆ (ประหยัด token)

แทนที่จะให้ AI อ่านเอกสารทั้งเล่มเข้า context (แพงมาก) ให้ค้นด้วยสคริปต์นี้ก่อน
แล้วอ่านเฉพาะช่วงที่ตรงประเด็น พร้อมชื่อไฟล์ต้นทางไว้อ้างอิง

วิธีค้น: keyword window search (ไม่ใช้ vector DB / ไม่ต้องลง dependency ใด ๆ)
  - ซอยเอกสารเป็นหน้าต่างซ้อนกัน (default 1200 ตัวอักษร, ซ้อน 200)
  - ให้คะแนน: เจอทั้งวลี = 3 คะแนน, เจอคำเดี่ยว = 1 คะแนน/ครั้ง
  - คืน top-k หน้าต่างที่คะแนนสูงสุด

ใช้:
    python3 corpus_search.py "คำค้น"                       # ค้นใน ./corpus
    python3 corpus_search.py "คำค้น" -k 8                   # เอา 8 อันดับแรก
    python3 corpus_search.py "คำค้น" --scope tgix           # เฉพาะไฟล์ที่ชื่อมี 'tgix'
    python3 corpus_search.py "คำค้น" --corpus-dir ~/vault   # ระบุโฟลเดอร์เอง
    python3 corpus_search.py "คำค้น" --json                 # ผลลัพธ์เป็น JSON
    python3 corpus_search.py --list                         # ดูว่ามีไฟล์อะไรใน corpus

ข้อจำกัด: เป็นการค้นแบบ keyword ไม่ใช่ semantic — คำพ้องความหมายจะค้นไม่เจอ
ถ้าค้นไม่เจอ ให้ลองคำอื่น/คำใกล้เคียงหลาย ๆ คำก่อนสรุปว่า "ไม่มีในเอกสาร"
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

EXTS = ("*.txt", "*.md")


def load_docs(corpus_dir: str, scope: str | None = None) -> dict[str, str]:
    docs: dict[str, str] = {}
    files: list[str] = []
    for ext in EXTS:
        files += glob.glob(os.path.join(corpus_dir, "**", ext), recursive=True)
    for f in sorted(files):
        rel = os.path.relpath(f, corpus_dir)
        if scope and scope.lower() not in rel.lower():
            continue
        try:
            with open(f, encoding="utf-8") as fh:
                docs[rel] = fh.read()
        except (UnicodeDecodeError, OSError) as e:
            print(f"!! ข้ามไฟล์ {rel}: {e}", file=sys.stderr)
    return docs


def windows(text: str, size: int, overlap: int):
    i, n = 0, len(text)
    step = max(size - overlap, 1)
    while i < n:
        yield i, text[i : i + size]
        i += step


def line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def search(
    query: str,
    corpus_dir: str,
    k: int = 5,
    scope: str | None = None,
    size: int = 1200,
    overlap: int = 200,
    excerpt_chars: int = 600,
) -> list[dict]:
    q = (query or "").strip()
    if not q:
        return []
    ql = q.lower()
    terms = [t.lower() for t in re.split(r"\s+", q) if t]

    hits = []
    for name, text in load_docs(corpus_dir, scope).items():
        for off, chunk in windows(text, size, overlap):
            cl = chunk.lower()
            score = cl.count(ql) * 3 + sum(cl.count(t) for t in terms)
            if score:
                hits.append((score, name, off, chunk, text))

    hits.sort(key=lambda x: -x[0])
    out = []
    for score, name, off, chunk, text in hits[:k]:
        excerpt = re.sub(r"[ \t]+", " ", chunk).strip()
        out.append(
            {
                "source": name,
                "line": line_of(text, off),
                "char_offset": off,
                "score": score,
                "excerpt": excerpt[:excerpt_chars],
            }
        )
    return out


def main() -> int:
    p = argparse.ArgumentParser(
        description="ค้นเอกสารใน corpus แล้วคืน excerpt สั้น ๆ (keyword window search)"
    )
    p.add_argument("query", nargs="?", help="คำหรือวลีที่ต้องการค้น")
    p.add_argument("-k", type=int, default=5, help="จำนวนผลลัพธ์สูงสุด (default 5)")
    p.add_argument("--scope", help="กรองเฉพาะไฟล์ที่ชื่อมีคำนี้ (เช่น 'tgix')")
    p.add_argument(
        "--corpus-dir",
        default=os.environ.get("CORPUS_DIR", "./corpus"),
        help="โฟลเดอร์เอกสาร (default: ./corpus หรือ env CORPUS_DIR)",
    )
    p.add_argument("--window", type=int, default=1200, help="ขนาดหน้าต่างค้น (ตัวอักษร)")
    p.add_argument("--overlap", type=int, default=200, help="ความซ้อนของหน้าต่าง")
    p.add_argument("--chars", type=int, default=600, help="ความยาว excerpt ที่คืน")
    p.add_argument("--json", action="store_true", help="พิมพ์ผลลัพธ์เป็น JSON")
    p.add_argument("--list", action="store_true", help="แสดงรายการไฟล์ใน corpus แล้วจบ")
    a = p.parse_args()

    corpus_dir = os.path.expanduser(a.corpus_dir)
    if not os.path.isdir(corpus_dir):
        print(
            f"!! ไม่พบโฟลเดอร์ corpus: {corpus_dir}\n"
            "   ระบุด้วย --corpus-dir หรือสร้างโฟลเดอร์ ./corpus แล้วนำเอกสารเข้าก่อน "
            "(ถ้าเป็น PDF ให้ใช้ skill thai-pdf-extract)",
            file=sys.stderr,
        )
        return 1

    if a.list:
        docs = load_docs(corpus_dir, a.scope)
        if not docs:
            print(f"corpus ว่าง: {corpus_dir}")
            return 1
        print(f"corpus: {corpus_dir}  ({len(docs)} ไฟล์)")
        for name, text in docs.items():
            print(f"  {name}  ({len(text):,} ตัวอักษร)")
        return 0

    if not a.query:
        p.print_usage()
        return 1

    res = search(
        a.query, corpus_dir, k=a.k, scope=a.scope,
        size=a.window, overlap=a.overlap, excerpt_chars=a.chars,
    )

    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0 if res else 1

    if not res:
        print(
            f'ไม่พบ "{a.query}" ใน {corpus_dir}\n'
            "หมายเหตุ: นี่คือการค้นแบบ keyword — ลองคำพ้อง/คำใกล้เคียงอีกสัก 2-3 คำ "
            "ก่อนสรุปว่าไม่มีในเอกสาร"
        )
        return 1

    print(f'query: "{a.query}"  | corpus: {corpus_dir}  | hits: {len(res)}\n')
    for i, r in enumerate(res, 1):
        print(f"[{i}] {r['source']}:{r['line']}  (score {r['score']})")
        print(f"    {r['excerpt']}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
