"""NEO Voice Backend — Text preprocessing pipeline."""

from __future__ import annotations

import re
import unicodedata

from config import MAX_CHARS_PER_CHUNK
from utils.markdown_cleaner import clean_markdown


# ───────────────────── Unicode normalization ──────────────────────


def normalize_unicode(text: str) -> str:
    """Normalize text to NFC, preserving Vietnamese diacritics."""
    text = unicodedata.normalize("NFC", text)
    # Replace smart quotes with standard
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    # Replace en-dash / em-dash with hyphen
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    return text


# ───────────────────── Text normalization ─────────────────────────


def normalize_text(text: str) -> str:
    """Basic text normalization for TTS."""
    text = normalize_unicode(text)

    # Collapse repeated spaces (preserve paragraph breaks)
    text = re.sub(r"[ \t]+", " ", text)

    # Limit repeated blank lines to max 2
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Convert ellipsis to pause marker
    text = re.sub(r"\.{3,}", "...", text)

    # Remove duplicated punctuation beyond 3
    text = re.sub(r"([!?]){3,}", r"\1\1\1", text)

    # Strip leading/trailing whitespace per line
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)

    return text.strip()


# ───────────────────── File reading ───────────────────────────────


def read_input_file(path: str) -> tuple[str, str | None]:
    """Read a text/markdown file. Returns (content, error_code)."""
    import os

    if not os.path.exists(path):
        return "", "FILE_READ_ERROR"

    ext = os.path.splitext(path)[1].lower()
    if ext not in (".txt", ".md"):
        return "", "FILE_UNSUPPORTED"

    # Try UTF-8, then UTF-8 with BOM
    for encoding in ("utf-8", "utf-8-sig"):
        try:
            with open(path, "r", encoding=encoding) as f:
                content = f.read()
            if ext == ".md":
                content = clean_markdown(content)
            return content, None
        except UnicodeDecodeError:
            continue
        except Exception:
            return "", "FILE_READ_ERROR"

    return "", "FILE_READ_ERROR"


# ───────────────────── Chunking ───────────────────────────────────


def chunk_text(text: str, engine: str = "vieneu") -> list[str]:
    """Split text into engine-appropriate chunks.
    
    Priority boundaries (from spec §12):
    1. Markdown heading (already converted to text.)
    2. Blank line / paragraph break
    3. Sentence punctuation
    4. Clause punctuation
    5. Hard split by char count
    """
    max_chars = MAX_CHARS_PER_CHUNK.get(engine, 900)

    # First pass: split by paragraph (double newline)
    paragraphs = re.split(r"\n\s*\n", text)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    chunks: list[str] = []
    for para in paragraphs:
        if len(para) <= max_chars:
            chunks.append(para)
        else:
            # Split long paragraphs by sentence
            chunks.extend(_split_by_sentence(para, max_chars))

    return chunks


def _split_by_sentence(text: str, max_chars: int) -> list[str]:
    """Split text into chunks at sentence boundaries."""
    # Split by sentence-ending punctuation (Vietnamese-aware)
    sentences = re.split(r"(?<=[.!?])\s+", text)

    chunks: list[str] = []
    current = ""

    for sentence in sentences:
        if not sentence.strip():
            continue

        if len(current) + len(sentence) + 1 <= max_chars:
            current = f"{current} {sentence}".strip() if current else sentence
        else:
            if current:
                chunks.append(current)

            if len(sentence) <= max_chars:
                current = sentence
            else:
                # Hard split by clause punctuation, then by char
                sub_chunks = _split_by_clause(sentence, max_chars)
                chunks.extend(sub_chunks[:-1])
                current = sub_chunks[-1] if sub_chunks else ""

    if current.strip():
        chunks.append(current.strip())

    return chunks


def _split_by_clause(text: str, max_chars: int) -> list[str]:
    """Split at clause boundaries (comma, semicolon, colon)."""
    parts = re.split(r"(?<=[,;:])\s+", text)
    chunks: list[str] = []
    current = ""

    for part in parts:
        if len(current) + len(part) + 1 <= max_chars:
            current = f"{current} {part}".strip() if current else part
        else:
            if current:
                chunks.append(current)
            if len(part) <= max_chars:
                current = part
            else:
                # Hard split
                chunks.extend(_hard_split(part, max_chars))
                current = ""

    if current.strip():
        chunks.append(current.strip())

    return chunks if chunks else [text]


def _hard_split(text: str, max_chars: int) -> list[str]:
    """Last resort: hard split by character count at word boundaries."""
    words = text.split()
    chunks: list[str] = []
    current = ""

    for word in words:
        if len(current) + len(word) + 1 <= max_chars:
            current = f"{current} {word}".strip() if current else word
        else:
            if current:
                chunks.append(current)
            current = word

    if current:
        chunks.append(current)

    return chunks if chunks else [text]


# ───────────────────── Full pipeline ──────────────────────────────


def preprocess(
    text: str,
    engine: str = "vieneu",
    is_markdown: bool = False,
) -> list[str]:
    """Full text pipeline: normalize → optional markdown clean → chunk.
    
    Returns list of text chunks ready for TTS engine.
    """
    if not text or not text.strip():
        return []

    if is_markdown:
        text = clean_markdown(text)

    text = normalize_text(text)

    if not text.strip():
        return []

    return chunk_text(text, engine)
