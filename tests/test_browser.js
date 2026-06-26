/**
 * NEO Voice — Browser UI Test via Playwright (Node.js)
 * Automated: navigate → select voice → enter text → create MP3 → verify
 */

const fs = require("fs");
const path = require("path");

const SCREENSHOTS = path.join(__dirname, "screenshots");
fs.mkdirSync(SCREENSHOTS, { recursive: true });

async function run() {
  let chromium;
  try {
    chromium = require("playwright").chromium;
  } catch {
    try {
      chromium = require("playwright-core").chromium;
    } catch {
      console.error("❌ Playwright not found. Install: npm i -g playwright");
      process.exit(1);
    }
  }

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });

  try {
    // Step 1: Navigate
    console.log("1️⃣  Navigating to http://localhost:5173...");
    await page.goto("http://localhost:5173", { waitUntil: "networkidle", timeout: 15000 });
    await page.screenshot({ path: `${SCREENSHOTS}/01_main_page.png` });
    console.log(`   📸 01_main_page.png — Title: ${await page.title()}`);

    // Step 2: Navigate to Create Voice if needed
    const navLink = await page.$('a:has-text("Tạo"), a:has-text("giọng"), [href*="create"]');
    if (navLink) {
      console.log("   Clicking nav link to Create Voice...");
      await navLink.click();
      await page.waitForTimeout(1000);
    }
    await page.screenshot({ path: `${SCREENSHOTS}/02_create_page.png` });
    console.log("   📸 02_create_page.png");

    // Step 3: Select a VieNeu voice
    console.log("\n2️⃣  Looking for VieNeu voice...");
    const voiceNames = ["Bình An", "Ngọc Lan", "Xuân Vĩnh", "Gia Bảo", "Ngọc Linh"];
    let clicked = false;
    for (const name of voiceNames) {
      const el = await page.$(`text=${name}`);
      if (el) {
        await el.click();
        console.log(`   ✅ Selected voice: ${name}`);
        clicked = true;
        await page.waitForTimeout(500);
        break;
      }
    }
    if (!clicked) console.log("   ⚠️  No VieNeu voice found by name");
    await page.screenshot({ path: `${SCREENSHOTS}/03_voice_selected.png` });
    console.log("   📸 03_voice_selected.png");

    // Step 4: Enter text
    console.log("\n3️⃣  Entering text...");
    const textarea = await page.$("textarea");
    if (textarea) {
      await textarea.fill("Xin chào, đây là bài kiểm tra tự động. Hệ thống NEO Voice hoạt động tốt.");
      console.log("   ✅ Text entered");
    } else {
      console.log("   ❌ No textarea found!");
    }
    await page.screenshot({ path: `${SCREENSHOTS}/04_text_entered.png` });
    console.log("   📸 04_text_entered.png");

    // Step 5: Click Tạo MP3
    console.log("\n4️⃣  Clicking 'Tạo MP3'...");
    const renderBtn = await page.$('button:has-text("Tạo MP3")');
    if (renderBtn) {
      const disabled = await renderBtn.getAttribute("disabled");
      if (disabled === null) {
        await renderBtn.click();
        console.log("   ✅ Clicked 'Tạo MP3'");
      } else {
        console.log("   ⚠️  Button is disabled");
      }
    } else {
      console.log("   ❌ Button not found");
    }
    await page.screenshot({ path: `${SCREENSHOTS}/05_after_click.png` });
    console.log("   📸 05_after_click.png");

    // Step 6: Wait for completion
    console.log("\n5️⃣  Waiting for job (max 40s)...");
    let completed = false;
    for (let i = 0; i < 27; i++) {
      await page.waitForTimeout(1500);
      
      const success = await page.$('text=Hoàn thành');
      const audio = await page.$('audio[controls]');
      const failed = await page.$('text=thất bại');

      if (success || audio) {
        console.log(`   ✅ Job completed after ~${Math.round((i+1)*1.5)}s!`);
        completed = true;
        break;
      }
      if (failed) {
        const errEl = await page.$('[style*="error"], [style*="dc2626"]');
        const msg = errEl ? await errEl.innerText() : "unknown";
        console.log(`   ❌ Job failed: ${msg}`);
        break;
      }

      // Progress check
      if (i % 3 === 0) {
        const progEl = await page.$('.progress-info');
        if (progEl) {
          const text = await progEl.innerText();
          if (text.trim()) console.log(`   ⏳ ${text.trim()}`);
        }
      }
    }
    await page.screenshot({ path: `${SCREENSHOTS}/06_result.png` });
    console.log("   📸 06_result.png");

    // Step 7: Verify UI elements
    console.log("\n6️⃣  Verifying result UI...");
    const audioPlayer = await page.$("audio[controls]");
    const downloadBtn = await page.$("a[download]");
    const filenameEl = await page.$("[style*='monospace']");

    if (audioPlayer) {
      const src = await audioPlayer.getAttribute("src");
      console.log(`   ✅ Audio player: ${(src || "").substring(0, 80)}`);
    } else {
      console.log("   ❌ No audio player");
    }

    if (downloadBtn) {
      const href = await downloadBtn.getAttribute("href");
      console.log(`   ✅ Download button: ${(href || "").substring(0, 80)}`);
    } else {
      console.log("   ❌ No download button");
    }

    if (filenameEl) {
      console.log(`   ✅ Filename: ${await filenameEl.innerText()}`);
    } else {
      console.log("   ❌ No filename display");
    }

    // Full page screenshot
    await page.screenshot({ path: `${SCREENSHOTS}/07_final.png`, fullPage: true });
    console.log("   📸 07_final.png (full page)");

    console.log(completed ? "\n🎉 BROWSER TEST PASSED!" : "\n⚠️  BROWSER TEST INCOMPLETE");

  } catch (err) {
    console.error(`\n❌ Test error: ${err.message}`);
    await page.screenshot({ path: `${SCREENSHOTS}/error.png` }).catch(() => {});
  } finally {
    await browser.close();
  }
}

run();
