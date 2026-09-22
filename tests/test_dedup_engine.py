"""
Unit tests for the deduplication engine.

Tests MD5 exact-match dedup, Jaccard trigram near-duplicate detection,
and edge cases like empty lists and all-duplicate inputs.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "rag")))

from dedup import dedup, jaccard, md5, trigrams

# ── MD5 Hashing ───────────────────────────────────────────────

class TestMD5:
    def test_deterministic(self):
        assert md5("hello world") == md5("hello world")

    def test_different_texts_different_hash(self):
        assert md5("hello") != md5("world")

    def test_empty_string(self):
        result = md5("")
        assert isinstance(result, str)
        assert len(result) == 32


# ── Trigram Generation ────────────────────────────────────────

class TestTrigrams:
    def test_short_text_empty(self):
        assert trigrams("one two") == set()

    def test_three_words(self):
        result = trigrams("one two three")
        assert len(result) == 1

    def test_case_insensitive(self):
        assert trigrams("The Quick Fox") == trigrams("the quick fox")

    def test_longer_text(self):
        result = trigrams("one two three four five")
        assert len(result) == 3


# ── Jaccard Similarity ───────────────────────────────────────

class TestJaccard:
    def test_identical_texts(self):
        text = "the quick brown fox jumps over the lazy dog"
        assert jaccard(text, text) == 1.0

    def test_completely_different(self):
        a = "alpha beta gamma delta epsilon"
        b = "one two three four five six seven"
        assert jaccard(a, b) == 0.0

    def test_partial_overlap(self):
        a = "the quick brown fox jumps"
        b = "the quick brown cat runs"
        score = jaccard(a, b)
        assert 0.0 < score < 1.0

    def test_empty_text(self):
        assert jaccard("", "hello world foo") == 0.0

    def test_both_empty(self):
        assert jaccard("", "") == 0.0


# ── Full Dedup Pipeline ──────────────────────────────────────

class TestDedup:
    def test_exact_duplicates_removed(self):
        chunks = [
            {"text": "This is a test chunk with enough words to form trigrams clearly"},
            {"text": "This is a test chunk with enough words to form trigrams clearly"},
            {"text": "This is a completely different chunk about accessibility features"},
        ]
        result = dedup(chunks)
        assert len(result) == 2

    def test_near_duplicates_removed(self):
        base = "WCAG 2.1 requires keyboard accessibility for all interactive elements on the page"
        near_dup = "WCAG 2.1 requires keyboard accessibility for all interactive controls on the page"
        different = "Color contrast must meet a minimum ratio of 4.5 to 1 for normal text"
        chunks = [{"text": base}, {"text": near_dup}, {"text": different}]
        result = dedup(chunks, threshold=0.5)  # Lower threshold to catch near-dupes
        assert len(result) <= 2

    def test_empty_list(self):
        assert dedup([]) == []

    def test_all_unique(self):
        chunks = [
            {"text": "First unique chunk about images and alt text requirements"},
            {"text": "Second unique chunk about keyboard navigation and focus"},
            {"text": "Third unique chunk about color contrast ratios and WCAG"},
        ]
        result = dedup(chunks)
        assert len(result) == 3

    def test_id_field_added(self):
        chunks = [{"text": "A test chunk with enough words to process correctly"}]
        result = dedup(chunks)
        assert "id" in result[0]
        assert isinstance(result[0]["id"], str)

    def test_trigrams_cleaned_up(self):
        chunks = [{"text": "A test chunk with enough words to generate some trigrams"}]
        result = dedup(chunks)
        assert "_trigrams" not in result[0]

    def test_single_word_chunks_skipped(self):
        chunks = [
            {"text": "hi"},
            {"text": "A real chunk with sufficient content to form trigrams for comparison"},
        ]
        result = dedup(chunks)
        assert len(result) == 1  # "hi" has no trigrams, gets dropped
