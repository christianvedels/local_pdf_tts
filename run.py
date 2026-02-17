"""Quick test script for pdf_to_speech."""

import logging
from pdf_to_speech import pdf_to_speech

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

pdf_to_speech(
    "../Sandbox/Breaking_the_HISCO_barrier.pdf",
    "../Sandbox/output.wav",
    # pages=(0, 4),
    voice="af_heart",
    on_progress=lambda i, n: print(f"Chunk {i + 1}/{n}"),
)

print("Done — saved to output.wav")
