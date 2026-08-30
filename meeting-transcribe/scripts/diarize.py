#!/usr/bin/env python3
"""
Speaker diarization using pyannote/speaker-diarization-3.1.

Called by transcribe.py --speakers; standalone usage:

    diarize.py input16k.wav segments.json [--num-speakers N] [--device auto|mps|cpu]

Writes JSON: {"segments": [{"start": s, "end": e, "speaker": "SPEAKER_00"}, ...]}

Requires a Hugging Face token (~/.cache/huggingface/token) whose account has
been granted access to the gated models pyannote/speaker-diarization-3.1 and
pyannote/segmentation-3.0 (request access on their Hugging Face pages first).

Re-executes itself inside the diarization venv automatically. Discovery order:
    $MEETING_DIAR_PY -> <skill>/.venv-diar/bin/python -> ~/projects/claude/asr/.venv-diar/bin/python
"""

import argparse
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent


def ensure_diar_env():
    if importlib.util.find_spec("pyannote") is not None:
        return
    cands = [os.environ.get("MEETING_DIAR_PY"),
             str(SKILL_DIR / ".venv-diar" / "bin" / "python"),
             str(Path.home() / "projects" / "claude" / "asr" / ".venv-diar" / "bin" / "python")]
    py = next((c for c in cands if c and Path(c).exists()), None)
    if py and os.path.realpath(py) != os.path.realpath(sys.executable):
        os.execv(py, [py] + sys.argv)
    sys.exit("ERROR: diarization venv not found. Run scripts/setup.sh first "
             "(or set MEETING_DIAR_PY).")


ensure_diar_env()
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

import torch  # noqa: E402

# pyannote 3.x checkpoints predate torch's weights_only default (torch >= 2.6)
# and fail to unpickle under it. The files come from the official pyannote
# repos on Hugging Face, so loading them the old way is acceptable here.
_orig_torch_load = torch.load


def _torch_load(*args, **kwargs):
    kwargs["weights_only"] = False
    return _orig_torch_load(*args, **kwargs)


torch.load = _torch_load

PIPELINE = "pyannote/speaker-diarization-3.1"


def pick_device(choice: str):
    if choice == "cpu":
        return torch.device("cpu")
    if choice == "mps" or (choice == "auto" and torch.backends.mps.is_available()):
        return torch.device("mps")
    return torch.device("cpu")


def run(wav: str, device, num_speakers):
    from pyannote.audio import Pipeline
    from pyannote.audio.pipelines.utils.hook import ProgressHook

    pipeline = Pipeline.from_pretrained(PIPELINE, use_auth_token=True)
    if pipeline is None:
        raise RuntimeError(
            f"Could not load {PIPELINE}. Check that your Hugging Face token has "
            "been granted access to the gated pyannote models."
        )
    pipeline.to(device)

    kwargs = {}
    if num_speakers:
        kwargs["num_speakers"] = num_speakers

    with ProgressHook() as hook:
        return pipeline(wav, hook=hook, **kwargs)


def main():
    ap = argparse.ArgumentParser(description="pyannote speaker diarization -> JSON")
    ap.add_argument("wav", help="16 kHz mono wav file")
    ap.add_argument("out_json", help="Output JSON path")
    ap.add_argument("--num-speakers", type=int, default=None)
    ap.add_argument("--device", default="auto", choices=["auto", "mps", "cpu"])
    args = ap.parse_args()

    device = pick_device(args.device)
    print(f"Diarizing on {device.type.upper()} ...", flush=True)
    t0 = time.time()

    try:
        annotation = run(args.wav, device, args.num_speakers)
    except Exception as e:
        if device.type == "mps":
            print(f"MPS failed ({e}); retrying on CPU ...", flush=True)
            annotation = run(args.wav, pick_device("cpu"), args.num_speakers)
        else:
            raise

    segments = [
        {"start": round(turn.start, 3), "end": round(turn.end, 3), "speaker": label}
        for turn, _, label in annotation.itertracks(yield_label=True)
    ]
    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump({"segments": segments}, f, ensure_ascii=False)

    speakers = sorted({s["speaker"] for s in segments})
    print(f"Diarization done in {time.time() - t0:.0f}s: "
          f"{len(segments)} turns, {len(speakers)} speakers ({', '.join(speakers)})",
          flush=True)


if __name__ == "__main__":
    main()
