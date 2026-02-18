"""Integration tests for the full TTS pipeline.

These tests require both toydata.pdf and the Kokoro model to be available.
They are marked slow and skipped by default — run with:

    pytest -m slow
"""

import pytest

# Mark every test in this module as slow
pytestmark = pytest.mark.slow


def _kokoro_available():
    try:
        from kokoro import KPipeline  # noqa: F401
        return True
    except ImportError:
        return False


skip_no_kokoro = pytest.mark.skipif(
    not _kokoro_available(), reason="Kokoro not installed"
)


@skip_no_kokoro
class TestSynthesise:
    def test_produces_audio(self):
        import numpy as np
        from pdf_to_speech.tts import load_pipeline, synthesise

        pipeline = load_pipeline()
        audio = synthesise("Hello world.", pipeline)
        assert isinstance(audio, np.ndarray)
        assert audio.dtype == np.float32
        assert len(audio) > 0

    def test_empty_text_raises(self):
        from pdf_to_speech.tts import load_pipeline, synthesise

        pipeline = load_pipeline()
        with pytest.raises(RuntimeError):
            synthesise("", pipeline)


@skip_no_kokoro
class TestPdfToSpeech:
    def test_wav_output(self, toydata_pdf, tmp_path):
        from pdf_to_speech import pdf_to_speech

        out = tmp_path / "test.wav"
        result = pdf_to_speech(toydata_pdf, out, pages=(0, 1), verbose=0)
        assert out.exists()
        assert out.stat().st_size > 1000
        assert result == out.resolve()

    def test_mp3_output(self, toydata_pdf, tmp_path):
        from pdf_to_speech import pdf_to_speech

        out = tmp_path / "test.mp3"
        result = pdf_to_speech(toydata_pdf, out, pages=(0, 1), verbose=0)
        assert out.exists()
        assert out.stat().st_size > 1000
        assert result == out.resolve()

    def test_on_progress_called(self, toydata_pdf, tmp_path):
        from pdf_to_speech import pdf_to_speech

        calls = []
        pdf_to_speech(
            toydata_pdf,
            tmp_path / "test.wav",
            pages=(0, 1),
            verbose=0,
            on_progress=lambda i, n: calls.append((i, n)),
        )
        assert len(calls) > 0
        # Last call should have i == total - 1
        assert calls[-1][0] == calls[-1][1] - 1

    def test_empty_pdf_raises(self, tmp_path):
        """A PDF with no extractable text should raise ValueError."""
        import fitz
        from pdf_to_speech import pdf_to_speech

        # Create a blank 1-page PDF
        doc = fitz.open()
        doc.new_page()
        blank_pdf = tmp_path / "blank.pdf"
        doc.save(str(blank_pdf))
        doc.close()

        with pytest.raises(ValueError, match="No text"):
            pdf_to_speech(blank_pdf, tmp_path / "out.wav", verbose=0)
