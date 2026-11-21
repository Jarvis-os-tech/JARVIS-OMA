const { app, BrowserWindow, ipcMain, screen } = require('electron');
const path = require('path');

// Explicitly align application name and Wayland app_id / window class to 'jarvis-drone'
app.name = 'jarvis-drone';

// Enforce single instance: terminate duplicate processes immediately
const gotSingleInstanceLock = app.requestSingleInstanceLock();
if (!gotSingleInstanceLock) {
  console.log('[Drone Main] Another instance of JARVIS Drone is already active. Exiting duplicate process.');
  app.exit(0);
}

app.on('second-instance', () => {
  // Reveal existing drone if another launch is attempted
  if (win && !win.isDestroyed()) {
    win.show();
    win.setAlwaysOnTop(true, 'screen-saver');
    if (win.webContents && !win.webContents.isDestroyed()) {
      win.webContents.send('drone-focus');
    }
  }
});

// Linux transparency switches
app.commandLine.appendSwitch('enable-transparent-visuals');

let win = null;
const WINDOW_SIZE = 96;
let isQuitting = false;

app.on('before-quit', () => {
  isQuitting = true;
});

function createWindow() {
  const primaryDisplay = screen.getPrimaryDisplay();
  const workArea = primaryDisplay.workArea || primaryDisplay.bounds;

  // Initial position: near top-right corner of primary workspace
  const initialX = Math.max(20, workArea.x + workArea.width - WINDOW_SIZE - 40);
  const initialY = Math.max(20, workArea.y + 60);

  win = new BrowserWindow({
    title: 'JARVIS Drone Companion',
    width: WINDOW_SIZE,
    height: WINDOW_SIZE,
    x: initialX,
    y: initialY,
    transparent: true,
    frame: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    hasShadow: false,
    resizable: false,
    focusable: false,
    backgroundColor: '#00000000',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    }
  });

  // Keep overlay pinned and on top across all workspaces
  win.setAlwaysOnTop(true, 'screen-saver');
  win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });

  // Prevent Super+W or window manager killactive close requests from destroying the window
  win.on('close', (event) => {
    if (!isQuitting) {
      event.preventDefault();
      return false;
    }
  });

  // Allow overriding port via env var (e.g. JARVIS_DRONE_PORT=8768) or CLI arg (--port=8768)
  const portArg = process.argv.find(arg => arg.startsWith('--port='));
  const customPort = process.env.JARVIS_DRONE_PORT || (portArg ? portArg.split('=')[1] : null);
  const loadOptions = customPort ? { query: { port: customPort } } : {};

  win.loadFile(path.join(__dirname, 'index.html'), loadOptions);

  win.on('closed', () => {
    win = null;
  });
}

// IPC handler: move window relatively
ipcMain.on('move-window-by', (event, { dx, dy }) => {
  if (win && !win.isDestroyed()) {
    const [curX, curY] = win.getPosition();
    win.setPosition(Math.round(curX + dx), Math.round(curY + dy));
  }
});

// IPC handler: set window absolute position
ipcMain.on('set-window-position', (event, { x, y }) => {
  if (win && !win.isDestroyed()) {
    win.setPosition(Math.round(x), Math.round(y));
  }
});

// IPC handler: query primary screen boundaries for movement clamping
ipcMain.handle('get-screen-bounds', () => {
  const primaryDisplay = screen.getPrimaryDisplay();
  return primaryDisplay.bounds;
});

// IPC handlers: visibility control (appear / disappear)
ipcMain.on('drone-disappear', () => {
  if (win && !win.isDestroyed()) {
    win.hide();
  }
});

ipcMain.on('drone-appear', () => {
  if (win && !win.isDestroyed()) {
    win.show();
    win.setAlwaysOnTop(true, 'screen-saver');
  }
});

ipcMain.handle('drone-is-visible', () => {
  return win && !win.isDestroyed() ? win.isVisible() : false;
});

app.whenReady().then(() => {
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
