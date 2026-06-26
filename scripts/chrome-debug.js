/**
 * Chrome Debug Launcher for Antigravity
 * Launches Chrome (installed) with remote debugging port 9222
 * Uses Playwright to properly manage the Chrome instance
 */
const { chromium } = require('playwright');

const PORT = 9222;

async function launchChromeDebug() {
  console.log('🚀 Launching Chrome with remote debugging on port ' + PORT + '...');
  
  const browser = await chromium.launch({
    headless: false,
    channel: 'chrome',
    args: [
      `--remote-debugging-port=${PORT}`,
      '--remote-allow-origins=*',
      '--disable-background-timer-throttling',
      '--no-first-run',
    ],
  });

  console.log('✅ Chrome launched! Remote debugging active on port ' + PORT);
  console.log('   WebSocket: ws://localhost:' + PORT + '/devtools/browser/...');
  console.log('   HTTP: http://localhost:' + PORT + '/json/version');
  console.log('');
  console.log('   Antigravity Browser Agent can now connect.');
  console.log('   Press Ctrl+C to close.');

  // Keep alive
  process.on('SIGINT', async () => {
    console.log('\nClosing Chrome...');
    await browser.close();
    process.exit(0);
  });

  // Prevent exit
  await new Promise(() => {});
}

launchChromeDebug().catch(err => {
  console.error('❌ Failed to launch Chrome:', err.message);
  process.exit(1);
});
