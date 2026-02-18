"""Quick test script for pdf_to_speech."""

from pdf_to_speech import pdf_to_speech

pdf_to_speech(
    "tests/fixtures/toydata.pdf",
    "output.mp3",
    voice="af_heart",
)

print("Done — saved to output.mp3")
