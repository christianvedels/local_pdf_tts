"""Tests for text chunking logic."""

from pdf_to_speech.core import chunk_text


def test_single_sentence_under_limit():
    text = "Hello world."
    chunks = chunk_text(text, max_chars=500)
    assert chunks == ["Hello world."]


def test_splits_on_sentence_boundary():
    text = "First sentence. Second sentence. Third sentence."
    chunks = chunk_text(text, max_chars=35)
    assert len(chunks) >= 2
    # Each chunk should be within limit (or a single sentence)
    for c in chunks:
        assert "." in c  # every chunk has at least one sentence


def test_respects_max_chars():
    sentences = [f"Sentence number {i}." for i in range(20)]
    text = " ".join(sentences)
    chunks = chunk_text(text, max_chars=100)
    # Most chunks should be within the limit
    for c in chunks:
        # A single sentence might exceed if it's too long on its own,
        # but our sentences are short so all should fit
        assert len(c) <= 100


def test_long_sentence_kept_intact():
    long = "A" * 600 + "."
    chunks = chunk_text(long, max_chars=500)
    # Should not be split (single sentence)
    assert len(chunks) == 1
    assert chunks[0] == long


def test_empty_input():
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_preserves_all_text():
    text = "Alpha bravo. Charlie delta. Echo foxtrot. Golf hotel."
    chunks = chunk_text(text, max_chars=30)
    reassembled = " ".join(chunks)
    # All words should appear
    for word in ["Alpha", "bravo", "Charlie", "delta", "Echo", "foxtrot", "Golf", "hotel"]:
        assert word in reassembled
