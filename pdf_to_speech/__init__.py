"""pdf_to_speech — Convert PDF documents to speech using Kokoro TTS."""

from .core import pdf_to_speech
from .tts import SAMPLE_RATE

__all__ = ["pdf_to_speech", "SAMPLE_RATE"]
