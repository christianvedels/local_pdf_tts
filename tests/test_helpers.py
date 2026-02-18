"""Tests for helper functions in core.py."""

import numpy as np

from pdf_to_speech.core import _fmt_duration, _silence
from pdf_to_speech.tts import SAMPLE_RATE


class TestFmtDuration:
    def test_seconds(self):
        assert _fmt_duration(42) == "42s"

    def test_seconds_rounds(self):
        assert _fmt_duration(0.4) == "0s"
        assert _fmt_duration(59.9) == "60s"  # rounds up

    def test_minutes(self):
        assert _fmt_duration(90) == "1m 30s"

    def test_minutes_zero_seconds(self):
        assert _fmt_duration(120) == "2m 00s"

    def test_hours(self):
        assert _fmt_duration(3661) == "1h 01m"

    def test_zero(self):
        assert _fmt_duration(0) == "0s"


class TestSilence:
    def test_default_duration(self):
        s = _silence()
        expected_samples = int(SAMPLE_RATE * 0.3)
        assert len(s) == expected_samples

    def test_custom_duration(self):
        s = _silence(1.0)
        assert len(s) == SAMPLE_RATE

    def test_dtype(self):
        s = _silence()
        assert s.dtype == np.float32

    def test_all_zeros(self):
        s = _silence()
        assert np.all(s == 0)
