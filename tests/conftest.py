"""Shared fixtures for the test suite."""

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
TOYDATA_PDF = FIXTURES / "toydata.pdf"


@pytest.fixture
def toydata_pdf():
    """Path to the compiled toydata PDF (skip if not yet compiled)."""
    if not TOYDATA_PDF.exists():
        pytest.skip("toydata.pdf not found — compile toydata.tex first")
    return TOYDATA_PDF
