"""Tests for the text pipeline: Markdown cleanup, chunking, normalization."""

import pytest
from services.text_pipeline import (
    normalize_unicode,
    clean_markdown,
    chunk_text,
    normalize_text,
)


class TestMarkdownCleanup:
    """Tests for Markdown cleanup following spec §12."""

    def test_remove_yaml_front_matter(self):
        text = "---\ntitle: Test\nauthor: AI\n---\n\nHello world."
        result = clean_markdown(text)
        assert "title" not in result
        assert "Hello world" in result

    def test_headings_become_text_with_pause(self):
        text = "# Chương 1\n\nNội dung."
        result = clean_markdown(text)
        assert "#" not in result
        assert "Chương 1" in result

    def test_remove_emphasis_markers(self):
        text = "**Lan** bước vào phòng."
        result = clean_markdown(text)
        assert "**" not in result
        assert "Lan bước vào phòng" in result

    def test_links_become_label_only(self):
        text = '[xem thêm](https://example.com)'
        result = clean_markdown(text)
        assert "https://example.com" not in result
        assert "xem thêm" in result

    def test_code_blocks_skipped(self):
        text = "Some text.\n\n```python\nprint('hello')\n```\n\nMore text."
        result = clean_markdown(text)
        assert "print" not in result
        assert "Some text" in result
        assert "More text" in result

    def test_full_markdown_example_from_spec(self):
        """From spec §12, Markdown cleanup example."""
        text = (
            "---\ntitle: Test\n---\n\n"
            "# Chương 1\n\n"
            '**Lan** nói: [xem thêm](https://example.com)\n\n'
            "```python\nprint(\"skip\")\n```"
        )
        result = clean_markdown(text)
        assert "#" not in result
        assert "**" not in result
        assert "https://example.com" not in result
        assert "print" not in result
        assert "Chương 1" in result
        assert "Lan" in result
        assert "xem thêm" in result


class TestUnicodeNormalization:
    """Tests for Unicode NFC normalization."""

    def test_nfc_normalization_preserves_vietnamese(self):
        text = "Xin chào, đây là NEO Voice."
        result = normalize_unicode(text)
        assert result == text

    def test_collapses_spaces(self):
        text = "Hello    world"
        result = normalize_text(text)
        assert "    " not in result


class TestChunking:
    """Tests for text chunking."""

    def test_short_text_single_chunk(self):
        text = "Xin chào."
        chunks = chunk_text(text, engine="vieneu")
        assert len(chunks) == 1

    def test_long_text_multiple_chunks(self):
        text = ". ".join(["Đây là một câu tiếng Việt khá dài"] * 50)
        chunks = chunk_text(text, engine="vieneu")
        assert len(chunks) > 1

    def test_chunk_order_preserved(self):
        text = "Đoạn một. Đoạn hai. Đoạn ba."
        chunks = chunk_text(text, engine="vieneu")
        joined = " ".join(c.strip() for c in chunks)
        assert "Đoạn một" in joined
        assert "Đoạn ba" in joined

    def test_no_chunk_exceeds_max(self):
        text = ". ".join(["Câu " + str(i) for i in range(100)])
        chunks = chunk_text(text, engine="vieneu")
        for chunk in chunks:
            assert len(chunk) <= 950, f"Chunk too long: {len(chunk)} chars"
