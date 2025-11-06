import { app, BrowserWindow, ipcMain } from 'electron';
import path from 'node:path';
import started from 'electron-squirrel-startup';
import fs from 'fs';

// Handle creating/removing shortcuts on Windows when installing/uninstalling.
if (started) {
  app.quit();
}

const createWindow = () => {
  // Create the browser window.
  const mainWindow = new BrowserWindow({
    width: 800,
    height: 600,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
    },
  });

  // and load the index.html of the app.
  if (MAIN_WINDOW_VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(MAIN_WINDOW_VITE_DEV_SERVER_URL);
  } else {
    mainWindow.loadFile(
      path.join(__dirname, `../renderer/${MAIN_WINDOW_VITE_NAME}/index.html`),
    );
  }

  // Open the DevTools.
  mainWindow.webContents.openDevTools();
};

// This method will be called when Electron has finished
// initialization and is ready to create browser windows.
// Some APIs can only be used after this event occurs.
app.on('ready', createWindow);

// Quit when all windows are closed, except on macOS. There, it's common
// for applications and their menu bar to stay active until the user quits
// explicitly with Cmd + Q.
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  // On OS X it's common to re-create a window in the app when the
  // dock icon is clicked and there are no other windows open.
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

// In this file you can include the rest of your app's specific main process
// code. You can also put them in separate files and import them here.
const IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.gif', '.webp'];

ipcMain.handle('read-user-data-file', async (event, relativePath) => {
  // (之前的程式碼... 保持不變)
  const filePath = path.join(app.getAppPath(), relativePath);
  if (!fs.existsSync(filePath)) {
    throw new Error(`文件未找到: ${filePath}`);
  }
  return fs.readFileSync(filePath);
});

ipcMain.handle('read-answer', async (event, relativePath) => {
  // (之前的程式碼... 保持不變)
  const answerPath = path.join(app.getAppPath(), 'answer');
  const filePath = path.join(answerPath, relativePath);
  if (!fs.existsSync(filePath)) {
    throw new Error(`文件未找到: ${filePath}`);
  }
  return fs.readFileSync(filePath);
});

// === 新增功能：讀取 data 資料夾下的所有圖片 ===
ipcMain.handle('list-images-in-data-dir', async () => {
  try {
    const dataDir = path.join(app.getAppPath(), 'data');
    console.log(dataDir)
    
    // 1. 確保 'data' 資料夾存在
    if (!fs.existsSync(dataDir)) {
      console.log("Data directory does not exist.");
      return []; // 回傳空陣列
    }

    // 2. 讀取資料夾
    const allFiles = fs.readdirSync(dataDir);

    // 3. 過濾出圖片檔案
    const imageFiles = allFiles.filter(file => {
      const ext = path.extname(file).toLowerCase();
      return IMAGE_EXTENSIONS.includes(ext);
    });

    // 4. 回傳相對於 userData 的路徑列表 (這很重要！)
    // 例如： ['data/image1.png', 'data/image2.jpg']
    const relativePaths = imageFiles.map(file => 
      path.join('data', file).replace(/\\/g, '/') // 確保使用 / 作為路徑分隔符
    );
    
    return relativePaths;

  } catch (error) {
    console.error('讀取 data 資料夾失敗:', error);
    throw error;
  }
});