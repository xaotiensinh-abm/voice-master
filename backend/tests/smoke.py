"""Quick smoke test for all backend core modules."""
import sys
import os

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

passed = 0
failed = 0

def test(name, fn):
    global passed, failed
    try:
        fn()
        print(f"  PASS: {name}")
        passed += 1
    except Exception as e:
        print(f"  FAIL: {name} - {e}")
        failed += 1

# --- Text Pipeline ---
def test_markdown():
    from services.text_pipeline import clean_markdown
    md = "# Chuong 1\n\n**Lan** noi: [xem them](https://example.com)"
    cleaned = clean_markdown(md)
    assert "#" not in cleaned
    assert "**" not in cleaned
    assert "https://example.com" not in cleaned
    assert "Chuong 1" in cleaned

def test_chunking():
    from services.text_pipeline import chunk_text
    text = ". ".join(["Day la mot cau tieng Viet dai hon mot chut de test chunking nhe"] * 20)
    chunks = chunk_text(text, engine="vieneu")
    assert len(chunks) >= 1

def test_unicode():
    from services.text_pipeline import normalize_unicode
    result = normalize_unicode("Xin chào")
    assert "chào" in result

# --- GPU ---
def test_gpu():
    from utils.gpu import detect_gpu
    gpu = detect_gpu()
    assert gpu.name is not None
    print(f"    GPU: {gpu.name}, VRAM: {gpu.vram_total_mb}MB")

# --- Audio Utils ---
def test_audio():
    from utils.audio import generate_output_filename, is_ffmpeg_available
    fname = generate_output_filename("test_script", "ngoc_lan")
    assert "ngoc_lan" in fname
    assert fname.endswith(".mp3")
    print(f"    ffmpeg available: {is_ffmpeg_available()}")

# --- Adapters ---
def test_adapters_import():
    from adapters.vieneu_adapter import VieneuAdapter
    from adapters.elevenlabs_adapter import ElevenLabsAdapter
    assert VieneuAdapter is not None
    assert ElevenLabsAdapter is not None

def test_vieneu_health():
    from adapters.vieneu_adapter import VieneuAdapter
    va = VieneuAdapter()
    h = va.health()
    assert h.status in ("available", "unavailable", "not_loaded", "dependency_missing")
    print(f"    VieNeu: {h.status}")

def test_elevenlabs_health():
    from adapters.elevenlabs_adapter import ElevenLabsAdapter
    ea = ElevenLabsAdapter()
    h = ea.health()
    assert h.status in ("not_configured", "available", "ready")
    print(f"    ElevenLabs: {h.status}")

# --- Security ---
def test_security():
    from utils.security import redact_string
    result = redact_string("sk_test_1234567890abcdef")
    assert "1234567890" not in result
    print(f"    Redacted: {result}")

# --- FastAPI App ---
def test_fastapi():
    from main import app
    assert app.title == "NEO Voice Local TTS"

# --- Engine Router ---
def test_router():
    from adapters.base import register_adapter, get_adapter
    from adapters.vieneu_adapter import VieneuAdapter
    register_adapter("vieneu", VieneuAdapter())
    adapter = get_adapter("vieneu:ngoc_lan")
    assert adapter is not None

# Run all tests
print("=" * 50)
print("NEO Voice Backend — Smoke Test")
print("=" * 50)

test("Markdown cleanup", test_markdown)
test("Text chunking", test_chunking)
test("Unicode normalization", test_unicode)
test("GPU detection", test_gpu)
test("Audio utils", test_audio)
test("Adapters import", test_adapters_import)
test("VieNeu health", test_vieneu_health)
test("ElevenLabs health", test_elevenlabs_health)
test("Security redaction", test_security)
test("FastAPI app creation", test_fastapi)
test("Engine router", test_router)

print("=" * 50)
print(f"Results: {passed} passed, {failed} failed")
if failed == 0:
    print("ALL TESTS PASSED!")
else:
    print("SOME TESTS FAILED!")
    sys.exit(1)
