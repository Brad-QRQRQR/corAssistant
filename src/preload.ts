// See the Electron documentation for details on how to use preload scripts:
// https://www.electronjs.org/docs/latest/tutorial/process-model#preload-scripts
import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('electronAPI', {
  readUserDataFile: (relativePath) => 
    ipcRenderer.invoke('read-user-data-file', relativePath),
  listImagesInDataDir: () => 
    ipcRenderer.invoke('list-images-in-data-dir')
});
