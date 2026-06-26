"""
NEO Voice — Browser UI Test via Playwright
Automated test: navigate, select voice, enter text, create MP3, verify result
"""
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

SCREENSHOTS_DIR = "D:/TQD-Voice/tests/screenshots"

import os
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})

        # Step 1: Navigate
        print("1️⃣ Navigating to http://localhost:5173...")
        page.goto("http://localhost:5173", wait_until="networkidle", timeout=15000)
        page.screenshot(path=f"{SCREENSHOTS_DIR}/01_main_page.png", full_page=False)
        print(f"   📸 Screenshot: 01_main_page.png")
        print(f"   Title: {page.title()}")

        # Step 2: Check if we need to navigate to Create Voice page
        nav_links = page.query_selector_all("a, button, [role='tab']")
        for link in nav_links:
            text = (link.inner_text() or "").strip()
            if "tạo" in text.lower() or "create" in text.lower() or "giọng" in text.lower():
                print(f"   Found nav link: '{text}' — clicking...")
                link.click()
                page.wait_for_timeout(1000)
                break

        page.screenshot(path=f"{SCREENSHOTS_DIR}/02_create_voice_page.png", full_page=False)
        print(f"   📸 Screenshot: 02_create_voice_page.png")

        # Step 3: Find and click a VieNeu voice card
        print("\n2️⃣ Looking for VieNeu voice cards...")
        voice_cards = page.query_selector_all("[class*='voice'], [class*='card']")
        clicked_voice = False
        
        # Try clicking by text content containing VieNeu voice names
        vieneu_names = ["Bình An", "Ngọc Lan", "Xuân Vĩnh", "Gia Bảo", "Thái Sơn", "Ngọc Linh"]
        for name in vieneu_names:
            el = page.query_selector(f"text={name}")
            if el:
                print(f"   Found voice: '{name}' — clicking...")
                el.click()
                page.wait_for_timeout(500)
                clicked_voice = True
                break
        
        if not clicked_voice:
            # Fallback: try any clickable element with 'vieneu' text
            el = page.query_selector("text=vieneu")
            if el:
                el.click()
                page.wait_for_timeout(500)
                clicked_voice = True
                print("   Clicked element with 'vieneu' text")

        page.screenshot(path=f"{SCREENSHOTS_DIR}/03_voice_selected.png", full_page=False)
        print(f"   📸 Screenshot: 03_voice_selected.png")
        print(f"   Voice selected: {clicked_voice}")

        # Step 4: Enter text
        print("\n3️⃣ Entering text...")
        textarea = page.query_selector("textarea")
        if textarea:
            textarea.fill("Xin chào, đây là bài kiểm tra tự động từ trình duyệt. Hệ thống NEO Voice đang hoạt động tốt.")
            print("   ✅ Text entered in textarea")
        else:
            print("   ❌ No textarea found!")
        
        page.screenshot(path=f"{SCREENSHOTS_DIR}/04_text_entered.png", full_page=False)
        print(f"   📸 Screenshot: 04_text_entered.png")

        # Step 5: Click "Tạo MP3" button
        print("\n4️⃣ Clicking 'Tạo MP3' button...")
        render_btn = page.query_selector("button.btn-render, button:has-text('Tạo MP3')")
        if render_btn:
            is_disabled = render_btn.get_attribute("disabled")
            print(f"   Button found, disabled={is_disabled}")
            if not is_disabled:
                render_btn.click()
                print("   ✅ Clicked 'Tạo MP3'")
            else:
                print("   ⚠️ Button is disabled — checking why...")
                page.screenshot(path=f"{SCREENSHOTS_DIR}/04b_button_disabled.png")
        else:
            print("   ❌ 'Tạo MP3' button not found!")
            # Debug: list all buttons
            buttons = page.query_selector_all("button")
            for btn in buttons[:10]:
                print(f"      - Button: '{(btn.inner_text() or '').strip()[:50]}'")

        page.screenshot(path=f"{SCREENSHOTS_DIR}/05_after_click.png", full_page=False)
        print(f"   📸 Screenshot: 05_after_click.png")

        # Step 6: Wait for job to complete
        print("\n5️⃣ Waiting for job to complete (max 30s)...")
        for i in range(20):
            time.sleep(1.5)
            # Check for completion indicators
            success_el = page.query_selector("text=Hoàn thành")
            error_el = page.query_selector("text=thất bại")
            audio_el = page.query_selector("audio")
            
            if success_el or audio_el:
                print(f"   ✅ Job completed after ~{int((i+1)*1.5)}s!")
                break
            if error_el:
                error_text = page.query_selector("[style*='error'], [style*='red']")
                msg = error_text.inner_text() if error_text else "unknown error"
                print(f"   ❌ Job failed after ~{int((i+1)*1.5)}s: {msg}")
                break
            
            # Check progress
            progress_el = page.query_selector(".progress-info")
            if progress_el:
                prog_text = progress_el.inner_text().strip()
                if prog_text and i % 3 == 0:
                    print(f"   ⏳ Progress: {prog_text}")

        page.screenshot(path=f"{SCREENSHOTS_DIR}/06_result.png", full_page=False)
        print(f"   📸 Screenshot: 06_result.png")

        # Step 7: Check final state
        print("\n6️⃣ Final state check...")
        audio_player = page.query_selector("audio[controls]")
        download_btn = page.query_selector("a[download]")
        filename_el = page.query_selector("[style*='monospace']")
        
        if audio_player:
            src = audio_player.get_attribute("src") or ""
            print(f"   ✅ Audio player found, src={src[:80]}...")
        else:
            print("   ❌ No audio player found")

        if download_btn:
            href = download_btn.get_attribute("href") or ""
            print(f"   ✅ Download button found, href={href[:80]}...")
        else:
            print("   ❌ No download button found")

        if filename_el:
            fname = filename_el.inner_text().strip()
            print(f"   ✅ Filename shown: {fname}")
        else:
            print("   ❌ No filename display found")

        # Final full-page screenshot
        page.screenshot(path=f"{SCREENSHOTS_DIR}/07_final.png", full_page=True)
        print(f"   📸 Screenshot: 07_final.png (full page)")

        browser.close()
        print("\n✅ Browser test complete!")

if __name__ == "__main__":
    run()
