"""Quick test script for pdf_to_speech."""

from pdf_to_speech import pdf_to_speech

pdf_to_speech(
    "../Sandbox/Breaking_the_HISCO_barrier.pdf",
    "../Sandbox/output.mp3",
    # pages=(0, 4),
    voice="af_heart",
)

print("Done — saved to ../Sandbox/output.mp3")
