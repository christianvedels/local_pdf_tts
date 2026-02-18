# Getting started with local_pdf_tts

This guide walks you through setting up the environment, installing dependencies, and using the library from scratch.

## Prerequisites

- **Python 3.11** (recommended; 3.10+ should work)
- **conda** (Miniconda or Anaconda) — needed to install ffmpeg cleanly on Windows/macOS
- A PDF you want to convert, such as an academic paper

---

## 1. Create and activate a conda environment

```bash
conda create -n pdf_tts python=3.11 -y
conda activate pdf_tts
```

## 2. Install ffmpeg

ffmpeg is required for MP3 export. Install it via conda so it is automatically on the PATH:

```bash
conda install ffmpeg -y
```

> If you only need WAV output you can skip this step.

## 3. Clone the repository

```bash
git clone https://github.com/christianvedels/local_pdf_tts
cd local_pdf_tts
```

## 4. Install Python dependencies

```bash
pip install -r requirements.txt
```

This installs:

| Package | Purpose |
|---|---|
| `kokoro>=0.9.4` | Local TTS model (82M parameters, Apache 2.0) |
| `PyMuPDF` | PDF text extraction |
| `scipy` / `numpy` | Audio array manipulation and WAV I/O |
| `pydub` | MP3 encoding (wraps ffmpeg) |
| `pytest` | Test runner |

The first time you run the library, Kokoro will download its model weights (~300 MB) from HuggingFace and cache them locally. This happens automatically.

---

## 5. Convert a PDF to speech

### Minimal example

```python
from pdf_to_speech import pdf_to_speech

pdf_to_speech("paper.pdf", "paper.mp3")
```

### Full example with all options

```python
from pdf_to_speech import pdf_to_speech

pdf_to_speech(
    "paper.pdf",
    "paper.mp3",            # .wav or .mp3 — format is auto-detected
    pages=(0, 10),          # first 10 pages only (0-indexed, stop exclusive)
    voice="af_heart",       # Kokoro voice identifier
    lang_code="a",          # "a" = American English (see README for full list)
    speed=1.0,              # playback speed multiplier
    max_chars_per_chunk=500,# max characters per TTS chunk
    verbose=2,              # 0=silent, 1=progress+ETA, 2=details, 3=debug
    on_progress=lambda i, n: print(f"{i+1}/{n}"),  # optional callback
)
```

### From the command line (quick smoke test)

```bash
python run.py
```

This converts the bundled toy PDF (`tests/fixtures/toydata.pdf`) and saves `output.mp3` in the project root.

---

## 6. Choosing a voice

Voices follow the pattern `{lang}{gender}_{name}`. The default is `af_heart` (American English, female).

A few popular choices:

| Voice | Description |
|---|---|
| `af_heart` | American English, female (default) |
| `af_bella` | American English, female |
| `am_michael` | American English, male |
| `bf_emma` | British English, female |
| `bm_george` | British English, male |

Full list: [VOICES.md on HuggingFace](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md)

---

## 7. Module overview

```
pdf_to_speech/
    __init__.py   # exports: pdf_to_speech, SAMPLE_RATE
    extract.py    # PDF text extraction and cleanup (PyMuPDF)
    tts.py        # Kokoro pipeline wrapper (load_pipeline, synthesise)
    core.py       # orchestration: extract → chunk → synthesise → save
tests/
    fixtures/
        toydata.tex   # LaTeX source for the test PDF
        toydata.pdf   # compiled fixture (included)
    conftest.py
    test_chunking.py  # text chunking logic
    test_helpers.py   # silence generation, duration formatting
    test_extract.py   # PDF extraction and text normalisation
    test_pipeline.py  # full TTS pipeline (marked slow, needs Kokoro)
```

The public API is a single function:

```python
from pdf_to_speech import pdf_to_speech

path = pdf_to_speech("paper.pdf", "paper.wav")
# returns pathlib.Path to the output file
```

---

## 8. Running the tests

```bash
# fast tests only (no Kokoro model required)
pytest

# full suite including TTS integration tests
pytest -m slow
```

---

## Troubleshooting

**`ffmpeg not found` when exporting MP3**
Make sure you installed ffmpeg via conda (`conda install ffmpeg -y`) and that the `pdf_tts` environment is active. On Windows, the library also checks `$CONDA_PREFIX/Library/bin` automatically.

**Kokoro downloads weights every run**
The weights are cached by HuggingFace in `~/.cache/huggingface/`. Once downloaded they are reused.

**Extracted text looks garbled**
Try passing a narrower `pages` range to isolate the problem page. Set `verbose=3` to see per-chunk text previews during synthesis.
