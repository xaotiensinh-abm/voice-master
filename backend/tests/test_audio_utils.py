"""Tests for audio export helpers."""

from utils.audio import export_encoded_audio_segments


def test_export_encoded_audio_segments_copies_single_mp3(tmp_path):
    source = tmp_path / "segment_0000.mp3"
    output = tmp_path / "output.mp3"
    source.write_bytes(b"ID3" + b"\0" * 2048)

    result = export_encoded_audio_segments([str(source)], str(output), "mp3")

    assert result == str(output)
    assert output.exists()
    assert output.stat().st_size == source.stat().st_size
