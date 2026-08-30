#!/bin/zsh
# One-time setup for the meeting-transcribe skill.
# Creates two virtualenvs inside the skill folder:
#   .venv-asr   : typhoon-asr + NeMo (Thai ASR)
#   .venv-diar  : pyannote.audio 3.x pinned stack (speaker diarization)
# Downloads roughly 3GB of dependencies on first run.

set -e
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$SKILL_DIR"

echo "== meeting-transcribe setup =="
echo "Skill dir: $SKILL_DIR"

# 1) ffmpeg
if ! command -v ffmpeg >/dev/null; then
  echo "ERROR: ffmpeg not found. Install first:  brew install ffmpeg"
  exit 1
fi
echo "ffmpeg: $(command -v ffmpeg)"

# 2) python 3.10-3.13
PY=""
for v in python3.13 python3.12 python3.11 python3.10; do
  if command -v $v >/dev/null; then PY=$v; break; fi
done
if [ -z "$PY" ]; then
  echo "ERROR: need python 3.10-3.13. Install first:  brew install python@3.13"
  exit 1
fi
echo "python: $PY ($($PY --version))"

# 3) ASR venv
if [ ! -x .venv-asr/bin/python ]; then
  echo "-- creating .venv-asr (typhoon-asr + NeMo, this takes a while) ..."
  $PY -m venv .venv-asr
  ./.venv-asr/bin/pip install -q --upgrade pip
  ./.venv-asr/bin/pip install typhoon-asr
else
  echo "-- .venv-asr already exists, skipping"
fi

# 4) diarization venv (pinned: pyannote 3.x is incompatible with newer
#    torchaudio (>=2.9 removed AudioMetaData) and huggingface_hub 1.x
#    (removed use_auth_token). Do NOT upgrade these pins.)
if [ ! -x .venv-diar/bin/python ]; then
  echo "-- creating .venv-diar (pyannote pinned stack) ..."
  $PY -m venv .venv-diar
  ./.venv-diar/bin/pip install -q --upgrade pip
  ./.venv-diar/bin/pip install "pyannote.audio<4" "torch==2.8.*" "torchaudio==2.8.*" "huggingface_hub<1.0"
else
  echo "-- .venv-diar already exists, skipping"
fi

# 5) smoke checks
./.venv-asr/bin/python -c "import importlib.util as u; assert u.find_spec('nemo'), 'nemo missing'" \
  && echo "ASR venv: OK"
./.venv-diar/bin/python -c "import pyannote.audio, torch, torchaudio; print('diar venv: pyannote', pyannote.audio.__version__, '| torch', torch.__version__)"

# 6) HF token reminder (needed for --speakers only)
if [ ! -f "$HOME/.cache/huggingface/token" ] && [ -z "$HF_TOKEN" ]; then
  cat <<'EOT'

NOTE: speaker mode (--speakers) needs a Hugging Face token with access to the
gated pyannote models. One-time steps:
  1. Create an account at https://huggingface.co and make a token (read scope)
  2. Request access on BOTH model pages:
       https://huggingface.co/pyannote/speaker-diarization-3.1
       https://huggingface.co/pyannote/segmentation-3.0
  3. Save the token:  mkdir -p ~/.cache/huggingface && echo "hf_xxx" > ~/.cache/huggingface/token
Plain transcription works without any token.
EOT
fi

echo
echo "Setup complete. Try:"
echo "  python3 \"$SKILL_DIR/scripts/transcribe.py\" your_meeting.m4a --outdir out"
