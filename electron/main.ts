import { app, BrowserWindow, ipcMain, dialog, shell } from 'electron';
import { spawn, ChildProcess } from 'child_process';
import path from 'path';
import fs from 'fs';

let mainWindow: BrowserWindow | null = null;
let pythonProcess: ChildProcess | null = null;

// Prevent duplicate instance
// const gotTheLock = app.requestSingleInstanceLock();
// if (!gotTheLock) {
//   console.log('Got the lock failed. Bypassing for dev...');
//   // app.quit();
// }

app.on('second-instance', () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.focus();
  }
});

function getBackendPort(): number {
  // Check runtime.json first
  const runtimePath = path.join(
    process.env.NEO_VOICE_HOME || path.join(process.env.APPDATA || '', 'Voice-Master'),
    'runtime.json'
  );
  try {
    if (fs.existsSync(runtimePath)) {
      const data = JSON.parse(fs.readFileSync(runtimePath, 'utf-8'));
      if (data.port) return data.port;
    }
  } catch {
    // fall through to default
  }
  // Check env
  if (process.env.NEO_VOICE_PORT) {
    return parseInt(process.env.NEO_VOICE_PORT, 10);
  }
  return 8757;
}

function startPythonBackend(): void {
  const port = getBackendPort();
  
  // Determine if we're packaged or in dev
  const isPackaged = app.isPackaged;
  const rootDir = isPackaged ? path.dirname(app.getPath('exe')) : path.join(app.getAppPath(), '..');
  
  const backendDir = path.join(rootDir, 'backend');
  const backendScript = path.join(backendDir, 'main.py');
  
  // Only start if the backend script exists
  if (fs.existsSync(backendScript)) {
    const portablePython = path.join(rootDir, 'python', 'python.exe');
    let pythonExecutable = 'python';
    let args = [backendScript, '--port', String(port)];

    if (fs.existsSync(portablePython)) {
      console.log('[Backend] Found portable Python runtime');
      pythonExecutable = portablePython;
    } else {
      console.log('[Backend] Using uv as fallback');
      pythonExecutable = 'uv';
      args = ['run', 'python', backendScript, '--port', String(port)];
    }

    // Enforce license only in the packaged .exe; running from source = demo.
    const backendEnv = { ...process.env };
    if (isPackaged) {
      backendEnv.VOICE_MASTER_LICENSE_ENFORCED = '1';
    }

    pythonProcess = spawn(pythonExecutable, args, {
      cwd: backendDir,
      stdio: 'pipe',
      env: backendEnv,
    });

    pythonProcess.stdout?.on('data', (data: Buffer) => {
      console.log(`[Backend] ${data.toString()}`);
    });

    pythonProcess.stderr?.on('data', (data: Buffer) => {
      console.error(`[Backend Error] ${data.toString()}`);
    });

    pythonProcess.on('close', (code: number | null) => {
      console.log(`[Backend] Process exited with code ${code}`);
      pythonProcess = null;
    });
  } else {
    console.log('[Backend] No backend script found, assuming external backend');
  }
}

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 1024,
    minHeight: 680,
    title: 'Voice-Master',
    icon: path.join(__dirname, '../public/icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: false,
    },
    frame: true,
    backgroundColor: '#F8FAFC',
    show: true,
  });

  // Dev or production
  if (process.env.VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL);
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// IPC Handlers
function registerIpcHandlers(): void {
  ipcMain.handle('open-file', async () => {
    const result = await dialog.showOpenDialog({
      properties: ['openFile'],
      filters: [
        { name: 'Text Files', extensions: ['txt', 'md'] },
      ],
    });
    if (result.canceled || result.filePaths.length === 0) return null;
    const filePath = result.filePaths[0];
    const content = fs.readFileSync(filePath, 'utf-8');
    return { path: filePath, content, name: path.basename(filePath) };
  });

  ipcMain.handle('select-output-dir', async () => {
    const result = await dialog.showOpenDialog({
      properties: ['openDirectory'],
    });
    if (result.canceled || result.filePaths.length === 0) return null;
    return result.filePaths[0];
  });

  ipcMain.handle('open-folder', async (_event, folderPath: string) => {
    await shell.openPath(folderPath);
  });

  ipcMain.handle('open-file-in-explorer', async (_event, filePath: string) => {
    shell.showItemInFolder(filePath);
  });

  ipcMain.handle('get-app-version', () => {
    return app.getVersion();
  });
}

app.whenReady().then(() => {
  registerIpcHandlers();
  startPythonBackend();
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// Graceful shutdown — kill Python process
app.on('before-quit', () => {
  if (pythonProcess) {
    console.log('[Backend] Shutting down Python backend...');
    pythonProcess.kill('SIGTERM');
    pythonProcess = null;
  }
});
