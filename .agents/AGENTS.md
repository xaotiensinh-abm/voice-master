# Voice-Master Project Rules

## [RULE: CHROME_DEBUG_AUTO]
Before invoking ANY browser subagent or using Chrome DevTools MCP tools:
1. Run `node D:/TQD-Voice/scripts/ensure-chrome-debug.js` as a background task
2. Wait 5 seconds for Chrome to be ready
3. Only THEN invoke the browser subagent

This is required because Chrome 149+ on Windows does NOT create DevToolsActivePort automatically.
The ensure-chrome-debug.js script handles: checking if already running, launching Chrome via Playwright, and creating the DevToolsActivePort file.

## [RULE: PROJECT_IDENTITY]
- Project name: **Voice-Master** (formerly NEO Voice)
- Backend: FastAPI on port 8757
- Frontend: Vite + React + Electron on port 5173
- Core TTS engine: VieNeu (primary), OmniVoice (secondary)
- MCP Server: port 8758 (for agent integration)
