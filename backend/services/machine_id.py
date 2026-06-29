"""Machine identity — stable per-machine id and the human-friendly machine_code.

See docs/licensing-packaging-spec.md §2. machine_code is what the user reads to
the author and what a license key is bound to.
"""

from __future__ import annotations

import base64
import hashlib
import platform
import uuid

from config import APP_SALT


def _machine_guid() -> str:
    """Stable hardware/OS identifier. Windows MachineGuid; else node()+MAC."""
    try:
        import winreg  # Windows only

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
            0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
        ) as k:
            val, _ = winreg.QueryValueEx(k, "MachineGuid")
            if val:
                return str(val)
    except Exception:
        pass
    # Fallback (non-Windows or registry unavailable)
    return f"{platform.node()}-{uuid.getnode()}"


def get_machine_id() -> str:
    """64-hex internal id = sha256(guid + salt)."""
    return hashlib.sha256((_machine_guid() + APP_SALT).encode("utf-8")).hexdigest()


def get_machine_code() -> str:
    """Human-friendly code 'XXXX-XXXX-XXXX-XXXX' (base32 of 80 bits)."""
    raw = hashlib.sha256(("MC:" + get_machine_id()).encode("utf-8")).digest()[:10]
    b32 = base64.b32encode(raw).decode("ascii").rstrip("=")  # 16 chars
    return "-".join(b32[i : i + 4] for i in range(0, 16, 4))
