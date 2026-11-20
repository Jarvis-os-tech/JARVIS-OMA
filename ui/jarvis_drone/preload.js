const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  setIgnoreMouseEvents: (ignore, options) => {
    ipcRenderer.send('set-ignore-mouse-events', ignore, options);
  },
  moveWindowBy: (dx, dy) => {
    ipcRenderer.send('move-window-by', { dx, dy });
  },
  setWindowPosition: (x, y) => {
    ipcRenderer.send('set-window-position', { x, y });
  },
  getScreenBounds: () => {
    return ipcRenderer.invoke('get-screen-bounds');
  },
  onGlobalCursor: (callback) => {
    ipcRenderer.on('global-cursor', (_, data) => callback(data));
  },
  disappear: () => {
    ipcRenderer.send('drone-disappear');
  },
  appear: () => {
    ipcRenderer.send('drone-appear');
  },
  isVisible: () => {
    return ipcRenderer.invoke('drone-is-visible');
  }
});
