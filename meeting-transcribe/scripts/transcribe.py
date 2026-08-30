#!/usr/bin/env python3
"""
Typhoon ASR batch transcriber for long Thai meeting audio (.m4a, .mp3, .wav, ...).

Fixes limitations of the official `typhoon-asr` CLI:
  1. It rejects .m4a despite its README (only .wav/.mp3/.flac/.ogg pass its check).
  2. It feeds the whole file to the model in one shot, which blows up memory on
     recordings longer than a few minutes.
  3. It reloads the model on every call and prints a raw NeMo object.

This script converts any ffmpeg-readable input to 16 kHz mono, splits it into
chunks at silent gaps (target ~40 s), loads the NeMo model once, transcribes all
chunks in batches, and writes one timestamped transcript per input file:
    <input_stem>.transcript.txt                (plain)
    <input_stem>.speakers.transcript.txt      (--speakers: pyannote diarization)

Usage:
    ./transcribe.py meeting_part1.m4a meeting_part2.m4a
    ./transcribe.py rec.m4a --outdir ./out --speakers --num-speakers 10

The script re-executes itself inside the ASR virtualenv automatically.
Venv discovery order (first match wins):
    $MEETING_ASR_PY  ->  <skill>/.venv-asr/bin/python  ->  ~/projects/claude/asr/.venv/bin/python
Run scripts/setup.sh once per machine to create the venvs.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
TARGET_SR = 16000


def find_asr_python() -> str | None:
    cands = [os.environ.get("MEETING_ASR_PY"),
             str(SKILL_DIR / ".venv-asr" / "bin" / "python"),
             str(Path.home() / "projects" / "claude" / "asr" / ".venv" / "bin" / "python")]
    return next((c for c in cands if c and Path(c).exists()), None)


def find_diar_python() -> str | None:
    cands = [os.environ.get("MEETING_DIAR_PY"),
             str(SKILL_DIR / ".venv-diar" / "bin" / "python"),
             str(Path.home() / "projects" / "claude" / "asr" / ".venv-diar" / "bin" / "python")]
    return next((c for c in cands if c and Path(c).exists()), None)


def ensure_asr_env():
    """Re-exec inside the ASR venv if NeMo is not importable here."""
    if importlib.util.find_spec("nemo") is not None:
        return
    py = find_asr_python()
    if py and os.path.realpath(py) != os.path.realpath(sys.executable):
        os.execv(py, [py] + sys.argv)
    sys.exit("ERROR: ASR venv not found. Run scripts/setup.sh first "
             "(or set MEETING_ASR_PY to a python that has typhoon-asr installed).")


def die(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def to_wav(src: Path, dst: Path):
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
           "-ar", str(TARGET_SR), "-ac", "1", "-c:a", "pcm_s16le", str(dst)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        die(f"ffmpeg failed on {src.name}: {r.stderr.strip()}")


def hms(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def split_into_chunks(y, sr, target_len=40.0, max_len=55.0, top_db=35):
    """Return (start, end) sample chunks cut only inside silent gaps."""
    import librosa

    speech = librosa.effects.split(y, top_db=top_db, frame_length=2048, hop_length=512)
    if len(speech) == 0:
        return []

    max_samples = int(max_len * sr)
    target_samples = int(target_len * sr)

    runs = []
    for s, e in speech:
        while e - s > max_samples:
            runs.append((s, s + max_samples))
            s += max_samples
        runs.append((s, e))

    chunks = []
    cur_start, cur_end = runs[0]
    for s, e in runs[1:]:
        if e - cur_start <= target_samples or (
            e - cur_start <= max_samples and s - cur_start < target_samples
        ):
            cur_end = e
        else:
            chunks.append((cur_start, cur_end))
            cur_start, cur_end = s, e
    chunks.append((cur_start, cur_end))
    return [(int(s), int(e)) for s, e in chunks]


def diarize_turns(wav: Path, tmp: Path, args, max_len: float):
    """Run pyannote diarization in its own venv; return [(start_s, end_s, speaker)]."""
    diar_py = find_diar_python()
    if not diar_py:
        die("speaker mode needs the diarization venv; run scripts/setup.sh "
            "(or set MEETING_DIAR_PY)")

    seg_json = tmp / "segments.json"
    cmd = [diar_py, str(SKILL_DIR / "scripts" / "diarize.py"), str(wav), str(seg_json)]
    if args.num_speakers:
        cmd += ["--num-speakers", str(args.num_speakers)]
    r = subprocess.run(cmd)
    if r.returncode != 0:
        die("diarization failed (see output above)")

    segs = json.loads(seg_json.read_text())["segments"]
    segs = sorted((s["start"], s["end"], s["speaker"]) for s in segs)

    merged = []
    for s, e, spk in segs:
        if (merged and spk == merged[-1][2]
                and s - merged[-1][1] <= 1.0 and e - merged[-1][0] <= max_len):
            merged[-1][1] = max(e, merged[-1][1])
        else:
            merged.append([s, e, spk])

    turns = []
    for s, e, spk in merged:
        while e - s > max_len:
            turns.append((s, s + max_len, spk))
            s += max_len
        if e - s >= 0.3:
            turns.append((s, e, spk))
    return turns


def load_model(model_name: str, device: str):
    print(f"Loading model {model_name} on {device.upper()} ...")
    import nemo.collections.asr as nemo_asr
    from nemo.utils import logging as nemo_logging

    nemo_logging.setLevel("ERROR")
    model = nemo_asr.models.ASRModel.from_pretrained(model_name=model_name, map_location=device)
    model.eval()
    return model


def hyp_text(item) -> str:
    if isinstance(item, str):
        return item
    if hasattr(item, "text"):
        return item.text
    return str(item)


def transcribe_file(model, src: Path, outdir: Path, args) -> Path:
    import numpy as np
    import librosa
    import soundfile as sf

    print(f"\n=== {src.name} ===")
    t0 = time.time()

    with tempfile.TemporaryDirectory(prefix="meeting_asr_") as tmp:
        tmp = Path(tmp)
        wav = tmp / "full.wav"
        to_wav(src, wav)

        y, sr = librosa.load(str(wav), sr=TARGET_SR, mono=True)
        duration = len(y) / sr
        print(f"Duration: {hms(duration)} ({duration:.0f}s)")

        labels = None
        if args.speakers:
            turns = diarize_turns(wav, tmp, args, max_len=args.chunk + 15)
            spk_order = []
            for _, _, spk in turns:
                if spk not in spk_order:
                    spk_order.append(spk)
            spk_name = {spk: f"speaker{i + 1}" for i, spk in enumerate(spk_order)}
            pad = int(0.15 * sr)
            chunks = [(max(0, int(s * sr) - pad), min(len(y), int(e * sr) + pad))
                      for s, e, _ in turns]
            labels = [spk_name[spk] for _, _, spk in turns]
        else:
            chunks = split_into_chunks(y, sr, target_len=args.chunk, max_len=args.chunk + 15)

        suffix = "speakers.transcript.txt" if args.speakers else "transcript.txt"
        if not chunks:
            print("No speech detected; writing empty transcript.")
            out = outdir / f"{src.stem}.{suffix}"
            out.write_text("", encoding="utf-8")
            return out

        chunk_files, chunk_starts = [], []
        for i, (s, e) in enumerate(chunks):
            c = y[s:e]
            peak = float(np.abs(c).max())
            if peak > 0:
                c = c / (peak + 1e-8)
            p = tmp / f"chunk_{i:04d}.wav"
            sf.write(str(p), c, sr)
            chunk_files.append(str(p))
            chunk_starts.append(s / sr)

        print(f"Split into {len(chunks)} chunks; transcribing (batch={args.batch}) ...")
        result = model.transcribe(audio=chunk_files, batch_size=args.batch)
        if isinstance(result, tuple):  # older RNNT API returns (best, all)
            result = result[0]
        texts = [hyp_text(h) for h in result]

    if labels:
        lines = [f"[{hms(start)}] {label}: {text.strip()}"
                 for start, label, text in zip(chunk_starts, labels, texts)
                 if text and text.strip()]
    else:
        lines = [f"[{hms(start)}] {text.strip()}"
                 for start, text in zip(chunk_starts, texts)
                 if text and text.strip()]
    out = outdir / f"{src.stem}.{suffix}"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    elapsed = time.time() - t0
    rtf = elapsed / duration if duration else 0
    print(f"Done in {elapsed:.0f}s (RTF {rtf:.2f}x) -> {out}")
    return out


def main():
    ap = argparse.ArgumentParser(description="Batch Thai transcription with Typhoon ASR")
    ap.add_argument("inputs", nargs="+", help="Audio files (anything ffmpeg reads)")
    ap.add_argument("--outdir", help="Output directory (default: next to each input file)")
    ap.add_argument("--chunk", type=float, default=40.0, help="Target chunk length in seconds (default 40)")
    ap.add_argument("--batch", type=int, default=4, help="Transcription batch size (default 4)")
    ap.add_argument("--model", default="scb10x/typhoon-asr-realtime", help="Model name on Hugging Face")
    ap.add_argument("--device", default="cpu", choices=["cpu", "cuda"], help="Inference device (default cpu)")
    ap.add_argument("--speakers", action="store_true",
                    help="Label speakers (speaker1, speaker2, ...) via pyannote diarization")
    ap.add_argument("--num-speakers", type=int, default=None,
                    help="Exact number of speakers, if known (improves diarization)")
    args = ap.parse_args()

    files = []
    for pattern in args.inputs:
        p = Path(pattern).expanduser()
        if not p.exists():
            die(f"file not found: {pattern}")
        files.append(p)

    model = load_model(args.model, args.device)

    outputs = []
    for f in files:
        outdir = Path(args.outdir).expanduser() if args.outdir else f.parent
        outdir.mkdir(parents=True, exist_ok=True)
        outputs.append(transcribe_file(model, f, outdir, args))

    print("\nAll transcripts:")
    for o in outputs:
        print(f"  {o}")


if __name__ == "__main__":
    ensure_asr_env()
    os.environ.setdefault("NEMO_LOG_LEVEL", "ERROR")
    main()
