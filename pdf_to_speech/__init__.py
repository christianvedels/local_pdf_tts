"""pdf_to_speech — Convert PDF documents to speech using Kokoro TTS."""

from .core import pdf_to_speech
from .latex import parse_latex_project
from .overleaf import latex_folder_to_speech
from .tts import SAMPLE_RATE

__all__ = ["pdf_to_speech", "parse_latex_project", "latex_folder_to_speech", "SAMPLE_RATE"]
