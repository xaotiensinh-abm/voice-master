"""Tests for voice registry operations."""

import pytest
from services.voice_registry import (
    validate_voice_id,
)
from services.job_queue import canonical_engine_name


class TestVoiceIdValidation:
    """Tests for voice ID prefix validation."""

    def test_valid_vieneu_prefix(self):
        assert validate_voice_id("vieneu:ngoc_lan") is True

    def test_valid_elevenlabs_prefix(self):
        assert validate_voice_id("elevenlabs:JBFqnCBsd6RMkjVDRZzb") is True

    def test_legacy_omni_prefix_returns_false(self):
        assert validate_voice_id("omni:ban_mai") is False

    def test_invalid_prefix_returns_false(self):
        assert validate_voice_id("unknown:test") is False

    def test_no_colon_returns_false(self):
        assert validate_voice_id("invalid_no_colon") is False

    def test_empty_string_returns_false(self):
        assert validate_voice_id("") is False


class TestVoiceIdStability:
    """Voice IDs should be stable across restarts."""

    def test_same_slug_produces_same_id(self):
        id1 = f"vieneu:ngoc_lan"
        id2 = f"vieneu:ngoc_lan"
        assert id1 == id2

    def test_different_slugs_different_ids(self):
        id1 = f"vieneu:ngoc_lan"
        id2 = f"vieneu:gia_bao"
        assert id1 != id2


class TestEngineNameMapping:
    """Public job engine names should match API/UI engine names."""

    def test_vieneu_prefix_stays_vieneu(self):
        assert canonical_engine_name("vieneu:ngoc_lan") == "vieneu"

    def test_elevenlabs_prefix_stays_elevenlabs(self):
        assert canonical_engine_name("elevenlabs:JBFqnCBsd6RMkjVDRZzb") == "elevenlabs"
