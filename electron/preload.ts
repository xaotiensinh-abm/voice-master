import { contextBridge, ipcRenderer } from 'electron';

export interface FileResult {
  path: string;
  content: string;
  name: string;
}

contextBridge.exposeInMainWorld('electronAPI', {
  openFile: (): Promise<FileResult | null> =>
    ipcRenderer.invoke('open-file'),
  selectOutputDir: (): Promise<string | null> =>
    ipcRenderer.invoke('select-output-dir'),
  openFolder: (folderPath: string): Promise<void> =>
    ipcRenderer.invoke('open-folder', folderPath),
  openFileInExplorer: (filePath: string): Promise<void> =>
    ipcRenderer.invoke('open-file-in-explorer', filePath),
  getAppVersion: (): Promise<string> =>
    ipcRenderer.invoke('get-app-version'),
});
