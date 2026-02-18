# local_pdf_tts

> **Note:** This project was built almost entirely by accepting changes suggested by [Claude Code](https://claude.ai/claude-code). It is not my own work in the traditional sense — I gave minimum feedback, and most of it was written and tested automatically.

Convert academic papers (PDFs) to speech audio for proofreading by ear. Runs locally on consumer hardware — no cloud API needed.

> **See [Getting_started.md](Getting_started.md) for a step-by-step setup guide.**

## How it works

1. **Extract** text from a PDF using PyMuPDF, with cleanup that handles hyphenated line breaks, paragraph detection, and filtering of tables/figures/page numbers.
2. **Chunk** the text on sentence boundaries.
3. **Synthesise** each chunk using [Kokoro](https://huggingface.co/hexgrad/Kokoro-82M) (82M parameter TTS model, Apache 2.0 license).
4. **Concatenate** the audio with short silence gaps and save as WAV or MP3.

Kokoro runs comfortably on CPU and fits in under 1 GB of VRAM if a GPU is available.

## Parameters

| Parameter | Default | Description |
|---|---|---|
| `pdf_path` | *(required)* | Path to the input PDF |
| `output_path` | *(required)* | Destination `.wav` or `.mp3` file |
| `voice` | `"af_heart"` | Kokoro voice identifier |
| `lang_code` | `"a"` | Language code (see below) |
| `speed` | `1.0` | Speech speed multiplier |
| `pages` | `None` (all) | Page range: `(start, stop)` tuple, `range`, or `None` |
| `max_chars_per_chunk` | `500` | Max characters per TTS chunk |
| `verbose` | `1` | Verbosity: `0` silent, `1` progress+ETA, `2` details, `3` debug |
| `on_progress` | `None` | Callback `(chunk_index, total_chunks)` |

## Voices

Kokoro ships with 47 voices across 9 languages. Voice names follow the pattern `{lang}{gender}_{name}`:

**American English** — `af_heart`, `af_alloy`, `af_aoede`, `af_bella`, `af_jessica`, `af_kore`, `af_nicole`, `af_nova`, `af_river`, `af_sarah`, `af_sky`, `am_adam`, `am_echo`, `am_eric`, `am_fenrir`, `am_liam`, `am_michael`, `am_onyx`, `am_puck`, `am_santa`

**British English** — `bf_alice`, `bf_emma`, `bf_isabella`, `bf_lily`, `bm_daniel`, `bm_fable`, `bm_george`, `bm_lewis`

Full list: [VOICES.md on HuggingFace](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md)

## Language codes

| Code | Language |
|---|---|
| `a` | American English |
| `b` | British English |
| `e` | Spanish |
| `f` | French |
| `h` | Hindi |
| `i` | Italian |
| `j` | Japanese |
| `p` | Brazilian Portuguese |
| `z` | Mandarin Chinese |

## PDF text extraction

The extractor is designed for academic papers and handles:

- Rejoining hyphenated words split across lines (`occupa-` + `tional` -> `occupational`)
- Merging PDF line wraps back into flowing paragraphs
- Preserving paragraph breaks (detected via line-length analysis)
- Filtering out tables (structural detection + short-fragment run detection)
- Filtering out page numbers and diagram label fragments

## License

This project uses [Kokoro](https://huggingface.co/hexgrad/Kokoro-82M) (Apache 2.0) and [PyMuPDF](https://pymupdf.readthedocs.io/) (AGPL-3.0).

---

*This project was built with [Claude Code](https://claude.ai/claude-code).*
