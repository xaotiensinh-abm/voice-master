/**
 * ensure-chrome-debug.js
 * Ensures Chrome is running with remote debugging before browser tests.
 * Auto-creates DevToolsActivePort file for Antigravity Browser Extension.
 * 
 * Usage: node scripts/ensure-chrome-debug.js
 * Returns exit 0 if ready, exit 1 if failed.
 */
const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = 9222;
const DAP_PATH = path.join(
  process.env.LOCALAPPDATA || '',
  'Google', 'Chrome', 'User Data', 'DevToolsActivePort'
);

async function checkPort() {
  return new Promise((resolve) => {
    http.get(`http://localhost:${PORT}/json/version`, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const json = JSON.parse(data);
          resolve(json);
        } catch { resolve(null); }
      });
    }).on('error', () => resolve(null));
  });
}

function writeDAP(versionInfo) {
  const ws = versionInfo?.webSocketDebuggerUrl || '';
  const browserId = ws.split('/').pop() || 'unknown';
  fs.writeFileSync(DAP_PATH, `${PORT}\n/devtools/browser/${browserId}`);
  console.log(`✅ DevToolsActivePort created at ${DAP_PATH}`);
}

async function launchChrome() {
  let chromium;
  try {
    chromium = require('playwright').chromium;
  } catch {
    try {
      chromium = require('playwright-core').chromium;
    } catch {
      console.error('❌ Playwright not installed. Run: pnpm add -D playwright');
      process.exit(1);
    }
  }

  console.log('🚀 Launching Chrome with remote debugging...');
  const browser = await chromium.launch({
    headless: false,
    channel: 'chrome',
    args: [
      `--remote-debugging-port=${PORT}`,
      '--remote-allow-origins=*',
      '--no-first-run',
      '--disable-background-timer-throttling',
    ],
  });

  // Wait for debug port to be ready
  for (let i = 0; i < 10; i++) {
    await new Promise(r => setTimeout(r, 1000));
    const info = await checkPort();
    if (info) {
      writeDAP(info);
      console.log(`✅ Chrome debug ready on port ${PORT}`);
      return browser;
    }
  }
  throw new Error('Chrome launched but debug port not responding');
}

async function main() {
  // Check if already running
  const existing = await checkPort();
  if (existing) {
    console.log(`✅ Chrome debug already active on port ${PORT}`);
    // Ensure DAP file exists
    if (!fs.existsSync(DAP_PATH)) {
      writeDAP(existing);
    }
    process.exit(0);
  }

  // Launch Chrome
  try {
    await launchChrome();
    console.log('Chrome running. Press Ctrl+C to stop.');
    // Keep alive
    await new Promise(() => {});
  } catch (err) {
    console.error(`❌ ${err.message}`);
    process.exit(1);
  }
}

main();
