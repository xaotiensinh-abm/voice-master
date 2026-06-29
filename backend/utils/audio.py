"""NEO Voice Backend — Audio utilities: WAV join, ffmpeg MP3 export."""

from __future__ import annotations

import logging
import os
import shutil
import struct
import subprocess
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from config import DEFAULT_BITRATE_KBPS, DEFAULT_SILENCE_MS

logger = logging.getLogger(__name__)


# ───────────────────── WAV helpers ────────────────────────────────


def validate_wav(path: str) -> bool:
    """Basic WAV validation: check RIFF header and minimum size."""
    try:
        with open(path, "rb") as f:
            header = f.read(12)
            if len(header) < 12:
                return False
            if header[:4] != b"RIFF" or header[8:12] != b"WAVE":
                return False
        return os.path.getsize(path) > 44  # at least header
    except Exception:
        return False


def read_wav_params(path: str) -> tuple[int, int, int]:
    """Read WAV sample rate, channels, bits per sample from header."""
    with open(path, "rb") as f:
        f.read(12)  # RIFF header
        # Find fmt chunk
        while True:
            chunk_id = f.read(4)
            if len(chunk_id) < 4:
                raise ValueError(f"Invalid WAV: {path}")
            chunk_size = struct.unpack("<I", f.read(4))[0]
            if chunk_id == b"fmt ":
                fmt_data = f.read(chunk_size)
                audio_format = struct.unpack("<H", fmt_data[0:2])[0]
                channels = struct.unpack("<H", fmt_data[2:4])[0]
                sample_rate = struct.unpack("<I", fmt_data[4:8])[0]
                bits_per_sample = struct.unpack("<H", fmt_data[14:16])[0]
                return sample_rate, channels, bits_per_sample
            else:
                f.read(chunk_size)
    raise ValueError(f"No fmt chunk in WAV: {path}")


def generate_silence_wav(duration_ms: int, sample_rate: int = 44100, path: str = "") -> str:
    """Generate a WAV file containing silence."""
    num_samples = int(sample_rate * duration_ms / 1000)
    data = b"\x00\x00" * num_samples  # 16-bit mono silence
    data_size = len(data)
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,
        1,  # PCM
        1,  # mono
        sample_rate,
        sample_rate * 2,  # byte rate
        2,  # block align
        16,  # bits per sample
        b"data",
        data_size,
    )
    with open(path, "wb") as f:
        f.write(header + data)
    return path


def join_wav_segments(
    wav_paths: list[str],
    output_path: str,
    silence_ms: int = DEFAULT_SILENCE_MS,
) -> str:
    """Join WAV segments with silence gaps using ffmpeg concat."""
    if not wav_paths:
        raise ValueError("No WAV segments to join")

    if len(wav_paths) == 1:
        shutil.copy2(wav_paths[0], output_path)
        return output_path

    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("ffmpeg không tìm thấy. Cài ffmpeg để xuất MP3.")

    # Create concat list file
    concat_dir = Path(output_path).parent
    concat_list = concat_dir / f"_concat_{os.getpid()}.txt"

    # Generate silence file
    sr, _, _ = read_wav_params(wav_paths[0])
    silence_path = str(concat_dir / f"_silence_{os.getpid()}.wav")
    generate_silence_wav(silence_ms, sr, silence_path)

    try:
        with open(concat_list, "w", encoding="utf-8") as f:
            for i, wav in enumerate(wav_paths):
                f.write(_concat_file_line(wav))
                if i < len(wav_paths) - 1:
                    f.write(_concat_file_line(silence_path))

        cmd = [
            ffmpeg, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list),
            "-c", "copy",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            logger.error("ffmpeg concat failed: %s", result.stderr)
            raise RuntimeError(f"ffmpeg concat failed: {result.stderr[:500]}")
        return output_path
    finally:
        concat_list.unlink(missing_ok=True)
        Path(silence_path).unlink(missing_ok=True)


# ───────────────────── MP3 export ─────────────────────────────────


def export_mp3(
    wav_path: str,
    mp3_path: str,
    bitrate_kbps: int = DEFAULT_BITRATE_KBPS,
) -> str:
    """Export WAV to MP3 via ffmpeg."""
    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("ffmpeg không tìm thấy. Cài ffmpeg để xuất MP3.")

    cmd = [
        ffmpeg, "-y",
        "-i", wav_path,
        "-codec:a", "libmp3lame",
        "-b:a", f"{bitrate_kbps}k",
        mp3_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        logger.error("ffmpeg export failed: %s", result.stderr)
        raise RuntimeError(f"Không xuất được MP3: {result.stderr[:500]}")

    # Validate output
    if not os.path.exists(mp3_path) or os.path.getsize(mp3_path) < 1024:
        raise RuntimeError("MP3 output quá nhỏ hoặc không tồn tại.")

    return mp3_path


def export_encoded_audio_segments(
    segment_paths: list[str],
    output_path: str,
    output_format: str = "mp3",
    bitrate_kbps: int = DEFAULT_BITRATE_KBPS,
) -> str:
    """Export one or more already-encoded audio segments to the requested output."""
    if not segment_paths:
        raise ValueError("No audio segments to export")

    output_format = output_format.lower()
    ffmpeg = _find_ffmpeg()

    if len(segment_paths) == 1:
        source = segment_paths[0]
        if output_format == "mp3" and source.lower().endswith(".mp3"):
            shutil.copy2(source, output_path)
            if not os.path.exists(output_path) or os.path.getsize(output_path) < 1024:
                raise RuntimeError("Audio output qua nho hoac khong ton tai.")
            return output_path
        if not ffmpeg:
            raise RuntimeError("ffmpeg khong tim thay de chuyen doi audio.")
        cmd = [ffmpeg, "-y", "-i", source]
        if output_format == "mp3":
            cmd += ["-codec:a", "libmp3lame", "-b:a", f"{bitrate_kbps}k"]
        cmd.append(output_path)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    else:
        if not ffmpeg:
            raise RuntimeError("ffmpeg khong tim thay de noi audio.")
        concat_dir = Path(output_path).parent
        concat_list = concat_dir / f"_concat_encoded_{os.getpid()}.txt"
        try:
            with open(concat_list, "w", encoding="utf-8") as f:
                for segment in segment_paths:
                    f.write(_concat_file_line(segment))
            cmd = [
                ffmpeg,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_list),
            ]
            if output_format == "mp3":
                cmd += ["-codec:a", "libmp3lame", "-b:a", f"{bitrate_kbps}k"]
            cmd.append(output_path)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        finally:
            concat_list.unlink(missing_ok=True)

    if result.returncode != 0:
        logger.error("ffmpeg audio export failed: %s", result.stderr)
        raise RuntimeError(f"Khong xuat duoc audio: {result.stderr[:500]}")
    if not os.path.exists(output_path) or os.path.getsize(output_path) < 1024:
        raise RuntimeError("Audio output qua nho hoac khong ton tai.")
    return output_path


def normalize_loudness(wav_path: str, output_path: str | None = None) -> str:
    """Optional loudness normalization via ffmpeg loudnorm filter."""
    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        return wav_path  # skip if no ffmpeg

    target = output_path or wav_path
    temp_path = wav_path + ".norm.wav"
    cmd = [
        ffmpeg, "-y",
        "-i", wav_path,
        "-af", "loudnorm=I=-16:LRA=11:TP=-1.5",
        temp_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode == 0:
        if target == wav_path:
            os.replace(temp_path, wav_path)
        else:
            shutil.move(temp_path, target)
        return target
    else:
        Path(temp_path).unlink(missing_ok=True)
        logger.warning("Loudness normalization failed, using original.")
        return wav_path


# ───────────────────── Output naming ──────────────────────────────


def change_audio_speed(wav_path: str, speed: float, output_path: str | None = None) -> str:
    """Adjust WAV playback speed with ffmpeg atempo while preserving pitch."""
    if abs(speed - 1.0) < 0.02:
        return wav_path

    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        logger.warning("Speed adjustment skipped because ffmpeg is unavailable.")
        return wav_path

    target = output_path or wav_path
    temp_path = wav_path + ".speed.wav"
    filters = _atempo_filters(speed)
    cmd = [ffmpeg, "-y", "-i", wav_path, "-filter:a", ",".join(filters), temp_path]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode == 0:
        if target == wav_path:
            os.replace(temp_path, wav_path)
        else:
            shutil.move(temp_path, target)
        return target

    Path(temp_path).unlink(missing_ok=True)
    logger.warning("Speed adjustment failed, using original audio: %s", result.stderr[:300])
    return wav_path


def generate_output_filename(
    source_name: str,
    voice_slug: str,
    ext: str = "mp3",
) -> str:
    """Generate output filename: <source>__<voice>__<timestamp>.mp3"""
    # Sanitize
    safe_source = _sanitize_filename(source_name)
    safe_voice = _sanitize_filename(voice_slug)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"{safe_source}__{safe_voice}__{ts}.{ext}"


def _sanitize_filename(name: str) -> str:
    """Make a string safe for Windows filenames."""
    import re
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = re.sub(r"\s+", "_", name)
    return name[:60] if name else "output"


# ───────────────────── Internals ──────────────────────────────────


def _concat_file_line(path: str) -> str:
    """Return one ffmpeg concat-list line, escaping paths conservatively."""
    safe = str(Path(path)).replace("\\", "/").replace("'", "'\\''")
    return f"file '{safe}'\n"


def _atempo_filters(speed: float) -> list[str]:
    """Build an ffmpeg atempo chain, keeping each factor in the supported range."""
    factors: list[float] = []
    remaining = max(0.1, speed)
    while remaining < 0.5:
        factors.append(0.5)
        remaining /= 0.5
    while remaining > 2.0:
        factors.append(2.0)
        remaining /= 2.0
    factors.append(remaining)
    return [f"atempo={factor:.4f}" for factor in factors]


@lru_cache(maxsize=1)
def _find_ffmpeg() -> str | None:
    """Find ffmpeg binary."""
    # Packaged build points here at the bundled ffmpeg (set by electron/main.ts).
    env_ff = os.environ.get("VOICE_MASTER_FFMPEG")
    if env_ff and os.path.isfile(env_ff):
        return env_ff
    path = shutil.which("ffmpeg")
    if path:
        return path
    # Check common Windows locations
    for candidate in [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
    ]:
        if os.path.isfile(candidate):
            return candidate
    return None


def is_ffmpeg_available() -> bool:
    """Check if ffmpeg is on PATH."""
    return _find_ffmpeg() is not None
