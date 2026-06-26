"""NEO Voice Backend — Markdown cleaner for TTS preprocessing."""

from __future__ import annotations

import re


def remove_yaml_front_matter(text: str) -> str:
    """Remove YAML front matter delimited by ---."""
    return re.sub(r"^---\s*\n.*?\n---\s*\n?", "", text, count=1, flags=re.DOTALL)


def headings_to_text(text: str) -> str:
    """Convert Markdown headings to plain text with pause (period + newline)."""
    # # Heading → Heading.
    return re.sub(r"^(#{1,6})\s+(.+)$", r"\2.", text, flags=re.MULTILINE)


def remove_emphasis(text: str) -> str:
    """Remove bold/italic markers: **text** → text, *text* → text, __text__ → text."""
    # Bold first (**), then italic (*)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"_(.+?)_", r"\1", text)
    return text


def links_to_label(text: str) -> str:
    """Replace [label](url) with label."""
    return re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)


def skip_code_blocks(text: str) -> str:
    """Remove fenced code blocks (```...```)."""
    return re.sub(r"```[\s\S]*?```", "", text)


def skip_html_tags(text: str) -> str:
    """Remove inline HTML tags."""
    return re.sub(r"<[^>]+>", "", text)


def bullets_to_sentences(text: str) -> str:
    """Convert bullet list items into separate sentences.
    
    - Item one  →  Item one.
    * Item two  →  Item two.
    """
    lines = text.split("\n")
    result = []
    for line in lines:
        stripped = line.strip()
        match = re.match(r"^[-*+]\s+(.+)$", stripped)
        if match:
            content = match.group(1).rstrip(".")
            result.append(f"{content}.")
        else:
            result.append(line)
    return "\n".join(result)


def clean_markdown(text: str) -> str:
    """Full Markdown cleanup pipeline for TTS input.
    
    Steps:
    1. Remove YAML front matter
    2. Skip fenced code blocks
    3. Skip HTML tags
    4. Convert headings to text with pause
    5. Remove emphasis markers
    6. Links → label only
    7. Bullets → separate sentences
    """
    text = remove_yaml_front_matter(text)
    text = skip_code_blocks(text)
    text = skip_html_tags(text)
    text = headings_to_text(text)
    text = remove_emphasis(text)
    text = links_to_label(text)
    text = bullets_to_sentences(text)
    return text.strip()
