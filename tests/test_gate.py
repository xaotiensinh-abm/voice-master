"""
NEO Voice — End-to-End Test Gate
Tests: Backend API health, VieNeu engine, job lifecycle, audio download
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "http://127.0.0.1:8757"
VITE = "http://localhost:5173"
RESULTS = {"pass": 0, "fail": 0, "skip": 0}

def test(name, fn):
    try:
        fn()
        RESULTS["pass"] += 1
        print(f"  ✅ PASS: {name}")
    except AssertionError as e:
        RESULTS["fail"] += 1
        print(f"  ❌ FAIL: {name} — {e}")
    except Exception as e:
        RESULTS["fail"] += 1
        print(f"  ❌ ERROR: {name} — {type(e).__name__}: {e}")

def api_get(path):
    req = urllib.request.Request(f"{BASE}{path}")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read()), resp.status

def api_post(path, body):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"{BASE}{path}", data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read()), resp.status

def http_get(url):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.read(), resp.status

# ══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("  NEO Voice — Test Gate")
print("=" * 60)

# ── Layer 1: Backend Health ──────────────────────────────────
print("\n🔍 Layer 1: Backend Health")

def test_health_endpoint():
    data, status = api_get("/health")
    assert status == 200, f"Expected 200, got {status}"
    assert data.get("status") == "ok", f"Expected status=ok, got {data.get('status')}"

def test_health_has_engines():
    data, _ = api_get("/health")
    assert "engines" in data, "Missing 'engines' in health response"
    engines = data["engines"]
    assert "vieneu" in engines, "Missing 'vieneu' engine"
    assert "elevenlabs" in engines, "Missing 'elevenlabs' engine"
    assert "omni" not in engines and "omnivoice" not in engines, "OmniVoice should be removed"

test("Health endpoint returns 200 OK", test_health_endpoint)
test("Health includes engine status", test_health_has_engines)

# ── Layer 2: Voice Listing ───────────────────────────────────
print("\n🔍 Layer 2: Voice Listing")

def test_voices_endpoint():
    data, status = api_get("/v1/voices")
    assert status == 200, f"Expected 200, got {status}"
    voices = data.get("voices", [])
    assert len(voices) > 0, "No voices returned"

def test_vieneu_voices_exist():
    data, _ = api_get("/v1/voices")
    voices = data.get("voices", [])
    vieneu_voices = [v for v in voices if v["engine"] == "vieneu"]
    assert len(vieneu_voices) >= 3, f"Expected >= 3 VieNeu voices, got {len(vieneu_voices)}"

def test_omni_voices_absent():
    data, _ = api_get("/v1/voices")
    voices = data.get("voices", [])
    omni_voices = [v for v in voices if v["engine"] == "omnivoice" or v["voice_id"].startswith("omni:")]
    assert len(omni_voices) == 0, f"Expected no OmniVoice voices, got {len(omni_voices)}"

test("Voices endpoint returns voices", test_voices_endpoint)
test("VieNeu has >= 3 voices", test_vieneu_voices_exist)
test("OmniVoice voices are absent", test_omni_voices_absent)

# ── Layer 3: VieNeu TTS Job Lifecycle ────────────────────────
print("\n🔍 Layer 3: VieNeu TTS Job Lifecycle")

JOB_ID = None

def test_create_vieneu_job():
    global JOB_ID
    body = {
        "voice_id": "vieneu:binh_an",
        "input": {"type": "text", "text": "Xin chào, đây là bài kiểm tra tự động."},
    }
    data, status = api_post("/v1/tts/jobs", body)
    assert status == 201, f"Expected 201, got {status}"
    assert "job_id" in data, "Missing job_id in response"
    JOB_ID = data["job_id"]

test("Create VieNeu job returns 201", test_create_vieneu_job)

def test_job_completes():
    assert JOB_ID, "No job_id from previous test"
    for i in range(30):  # max 45 seconds
        data, _ = api_get(f"/v1/tts/jobs/{JOB_ID}")
        if data["status"] == "completed":
            assert data["output_path"], "Completed but no output_path"
            assert data["progress"] == 1.0, f"Progress should be 1.0, got {data['progress']}"
            return
        if data["status"] == "failed":
            error_info = data.get("error", "unknown")
            raise AssertionError(f"Job failed: {error_info}")
        time.sleep(1.5)
    raise AssertionError(f"Job did not complete in 45s, last status: {data['status']}")

test("VieNeu job completes successfully", test_job_completes)

def test_job_audio_download():
    assert JOB_ID, "No job_id from previous test"
    audio_bytes, status = http_get(f"{BASE}/v1/tts/jobs/{JOB_ID}/audio")
    assert status == 200, f"Expected 200, got {status}"
    assert len(audio_bytes) > 1000, f"Audio too small ({len(audio_bytes)} bytes), likely empty"
    # Check MP3 magic bytes (ID3 or 0xFF 0xFB)
    assert audio_bytes[:3] == b"ID3" or audio_bytes[:2] == b"\xff\xfb", \
        f"Not valid MP3 (header: {audio_bytes[:4].hex()})"

test("Audio download returns valid MP3", test_job_audio_download)

def test_output_file_exists():
    assert JOB_ID, "No job_id from previous test"
    data, _ = api_get(f"/v1/tts/jobs/{JOB_ID}")
    path = data.get("output_path", "")
    assert os.path.exists(path), f"Output file not found: {path}"
    size = os.path.getsize(path)
    assert size > 1000, f"Output file too small: {size} bytes"

test("Output MP3 file exists on disk", test_output_file_exists)

# ── Layer 4: Frontend Accessibility ──────────────────────────
print("\n🔍 Layer 4: Frontend Accessibility")

def test_vite_dev_server():
    try:
        body, status = http_get(VITE)
        assert status == 200, f"Expected 200, got {status}"
        html = body.decode("utf-8", errors="ignore")
        assert "<html" in html.lower() or "<!doctype" in html.lower(), "Not HTML response"
    except urllib.error.URLError:
        raise AssertionError("Vite dev server not reachable at localhost:5173")

def test_frontend_has_react_root():
    body, _ = http_get(VITE)
    html = body.decode("utf-8", errors="ignore")
    assert 'id="root"' in html or 'id="app"' in html, "No React root element found"

test("Vite dev server is running", test_vite_dev_server)
test("Frontend has React root element", test_frontend_has_react_root)

# ── Layer 5: GPU Detection ───────────────────────────────────
print("\n🔍 Layer 5: GPU Detection")

def test_gpu_detected():
    data, _ = api_get("/health")
    gpu = data.get("gpu", {})
    assert gpu.get("detected") == True, f"GPU not detected: {gpu}"
    assert gpu.get("name"), "GPU name missing"

def test_gpu_cuda_available():
    data, _ = api_get("/health")
    gpu = data.get("gpu", {})
    assert gpu.get("cuda_available") == True, f"CUDA not available: {gpu}"

test("GPU is detected", test_gpu_detected)
test("CUDA is available", test_gpu_cuda_available)

# ══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
total = RESULTS["pass"] + RESULTS["fail"] + RESULTS["skip"]
print(f"  Results: {RESULTS['pass']}/{total} passed, {RESULTS['fail']} failed, {RESULTS['skip']} skipped")
if RESULTS["fail"] > 0:
    print("  ❌ TEST GATE FAILED")
    sys.exit(1)
else:
    print("  ✅ TEST GATE PASSED")
    sys.exit(0)
