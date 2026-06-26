"""Voice-Master Backend — VieNeu model download manager.

Handles the first-run download of the VieNeu-TTS v3 Turbo model from the
HuggingFace Hub. The model is NOT bundled with the installer; it is fetched on
demand into the standard HuggingFace cache (~/.cache/huggingface).

Scope (locked, see docs/feature-plan-model-download.md):
- Turbo only — fixed repo, no backbone selection.
- No cancel — a download runs to completion or fails (HF resumes on retry).
- Cache dir is the HF default; not configurable here.
"""

from __future__ import annotations

import logging
import shutil
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

# Default backbone repo used by `Vieneu(mode="v3turbo")` (vieneu/v3turbo.py).
# The whole repo is fetched so both the ONNX (CPU) and PyTorch (GPU) paths work
# offline afterwards.
REPO_ID = "pnnbao-ump/VieNeu-TTS-v3-Turbo"

# ───────────────────── Shared download state ──────────────────────
# Guarded by _lock. state ∈ {idle, downloading, done, error}.
_lock = threading.Lock()
_state: dict = {"state": "idle", "error": None}
_thread: threading.Thread | None = None

# Cheap caches so /health polling does not re-stat the cache or hit the network.
_downloaded_cache: bool | None = None
_total_bytes_cache: int | None = None


# ───────────────────── Cache-dir helpers ──────────────────────────


def _repo_cache_dir() -> Path:
    """Path of this repo's folder inside the HF hub cache."""
    from huggingface_hub.constants import HF_HUB_CACHE

    folder = "models--" + REPO_ID.replace("/", "--")
    return Path(HF_HUB_CACHE) / folder


def _dir_size(path: Path) -> int:
    """Total bytes of all files under ``path`` (follows nothing; counts blobs)."""
    if not path.exists():
        return 0
    total = 0
    for p in path.rglob("*"):
        try:
            if p.is_file():
                total += p.stat().st_size
        except OSError:
            continue
    return total


def _check_downloaded() -> bool:
    """True if the repo snapshot is fully present in the local cache."""
    try:
        from huggingface_hub import snapshot_download

        snapshot_download(repo_id=REPO_ID, local_files_only=True)
        return True
    except Exception:
        return False


def is_downloaded(refresh: bool = False) -> bool:
    """Whether the model is cached locally (memoized)."""
    global _downloaded_cache
    if _downloaded_cache is not None and not refresh:
        return _downloaded_cache
    _downloaded_cache = _check_downloaded()
    return _downloaded_cache


def get_total_bytes(refresh: bool = False) -> int:
    """Estimated total download size in bytes (memoized; 0 if unknown/offline)."""
    global _total_bytes_cache
    if _total_bytes_cache is not None and not refresh:
        return _total_bytes_cache
    try:
        from huggingface_hub import HfApi

        info = HfApi().model_info(REPO_ID, files_metadata=True)
        total = 0
        for sibling in info.siblings or []:
            lfs = getattr(sibling, "lfs", None)
            size = (lfs.get("size") if isinstance(lfs, dict) else getattr(lfs, "size", None)) \
                if lfs else getattr(sibling, "size", None)
            total += int(size or 0)
        _total_bytes_cache = total
    except Exception as e:
        logger.warning("model_info size estimate failed: %s", e)
        _total_bytes_cache = 0
    return _total_bytes_cache


# ───────────────────── Download worker ────────────────────────────


def _download_worker() -> None:
    global _downloaded_cache
    try:
        from huggingface_hub import snapshot_download

        logger.info("Downloading VieNeu model %s ...", REPO_ID)
        snapshot_download(repo_id=REPO_ID)  # HF resumes partial downloads on retry
        _downloaded_cache = True
        with _lock:
            _state["state"] = "done"
            _state["error"] = None
        logger.info("VieNeu model %s download complete", REPO_ID)
    except Exception as e:  # offline, disk full, auth, etc.
        logger.error("VieNeu model download failed: %s", e)
        with _lock:
            _state["state"] = "error"
            _state["error"] = str(e)


def start_download() -> dict:
    """Start (or no-op if already running/done) the background model download."""
    global _thread

    if is_downloaded():
        with _lock:
            _state["state"] = "done"
            _state["error"] = None
        return get_status()

    with _lock:
        if _state["state"] == "downloading" and _thread is not None and _thread.is_alive():
            return _progress_locked()
        _state["state"] = "downloading"
        _state["error"] = None
        _thread = threading.Thread(target=_download_worker, name="vieneu-model-dl", daemon=True)
        _thread.start()
        return _progress_locked()


def _progress_locked() -> dict:
    """Build a progress dict. Caller must hold _lock."""
    total = get_total_bytes()
    downloaded = _dir_size(_repo_cache_dir())
    state = _state["state"]
    # If the model is already present (e.g. from a prior session) report it as
    # done rather than a stale partial percent from the cache-dir heuristic.
    if state != "downloading" and is_downloaded():
        state = "done"
    # While downloading, cache size can briefly exceed the LFS estimate (refs,
    # metadata); clamp percent to [0, 100].
    if state == "done":
        percent = 100.0
    elif total > 0:
        percent = max(0.0, min(100.0, downloaded / total * 100.0))
    else:
        percent = 0.0
    return {
        "state": state,
        "downloaded_bytes": downloaded,
        "total_bytes": total,
        "percent": round(percent, 1),
        "error": _state["error"],
    }


def get_progress() -> dict:
    """Current download progress snapshot."""
    with _lock:
        return _progress_locked()


def get_status() -> dict:
    """Static status: whether the model is present, size, and cache path."""
    downloaded = is_downloaded()
    with _lock:
        state = _state["state"]
        error = _state["error"]
    return {
        "repo_id": REPO_ID,
        "downloaded": downloaded,
        "total_bytes": get_total_bytes(),
        "cache_path": str(_repo_cache_dir()),
        "state": "done" if downloaded else state,
        "error": error,
    }


def delete() -> dict:
    """Remove the cached model to free space / force a fresh re-download."""
    global _downloaded_cache
    with _lock:
        if _state["state"] == "downloading":
            raise RuntimeError("Đang tải mô hình, không thể xoá lúc này.")
    repo_dir = _repo_cache_dir()
    if repo_dir.exists():
        shutil.rmtree(repo_dir, ignore_errors=True)
    _downloaded_cache = False
    with _lock:
        _state["state"] = "idle"
        _state["error"] = None
    return get_status()
