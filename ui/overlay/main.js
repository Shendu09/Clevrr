/**
 * Clevrr Overlay — Electron Main Process
 * 
 * Handles:
 * - Transparent overlay window creation
 * - Hotkey registration (Win+Shift+Space)
 * - WebSocket client for Python backend
 * - IPC between main and renderer processes
 */

const { app, BrowserWindow, ipcMain, globalShortcut } = require('electron');
const path = require('path');
const WebSocket = require('ws');

let mainWindow = null;
let ws = null;
let isOverlayVisible = false;

// WebSocket configuration
const WS_HOST = 'ws://localhost:9999';
const RECONNECT_INTERVAL = 3000; // 3 seconds
const MAX_RECONNECT_ATTEMPTS = 5;
let reconnectAttempts = 0;

console.log('[CLEVRR OVERLAY] Starting Electron app');

/**
 * Initialize WebSocket connection to Python backend
 */
function initWebSocket() {
  console.log('[CLEVRR OVERLAY] Connecting to Python backend at', WS_HOST);
  
  ws = new WebSocket(WS_HOST);
  
  ws.onopen = () => {
    console.log('[CLEVRR OVERLAY] WebSocket connected');
    reconnectAttempts = 0;
    
    // Notify renderer that backend is ready
    if (mainWindow) {
      mainWindow.webContents.send('backend-connected');
    }
  };
  
  ws.onmessage = (event) => {
    // Forward all backend messages to renderer
    if (mainWindow) {
      mainWindow.webContents.send('backend-message', event.data);
    }
  };
  
  ws.onerror = (error) => {
    console.error('[CLEVRR OVERLAY] WebSocket error:', error.message);
  };
  
  ws.onclose = () => {
    console.log('[CLEVRR OVERLAY] WebSocket disconnected. Attempting reconnect...');
    
    if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
      reconnectAttempts++;
      setTimeout(initWebSocket, RECONNECT_INTERVAL);
    } else {
      console.error('[CLEVRR OVERLAY] Failed to connect after', MAX_RECONNECT_ATTEMPTS, 'attempts');
    }
  };
}

/**
 * Create the transparent overlay window
 */
function createOverlayWindow() {
  mainWindow = new BrowserWindow({
    width: 1920,
    height: 1080,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      enableRemoteModule: false,
    },
    transparent: true,
    frame: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    fullscreenable: false,
    resizable: false,
    movable: false,
    focusable: true,
    show: false,
  });

  mainWindow.loadFile('index.html');

  // Show dev tools in development
  if (process.argv.includes('--dev')) {
    mainWindow.webContents.openDevTools();
  }

  // Handle window closed
  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  return mainWindow;
}

/**
 * Register hotkey: Win+Shift+Space (Windows/Linux)
 * or Cmd+Shift+Space (macOS)
 */
function registerHotkeys() {
  let hotkey = 'CommandOrControl+Shift+Space';
  
  const ret = globalShortcut.register(hotkey, () => {
    console.log('[HOTKEY] Win+Shift+Space pressed');
    
    if (mainWindow) {
      if (isOverlayVisible) {
        hideOverlay();
      } else {
        showOverlay();
      }
    }
  });

  if (!ret) {
    console.error('[HOTKEY] Failed to register hotkey:', hotkey);
  } else {
    console.log('[HOTKEY] Registered hotkey:', hotkey);
  }
}

/**
 * Show the overlay and focus input
 */
function showOverlay() {
  if (mainWindow) {
    mainWindow.show();
    isOverlayVisible = true;
    mainWindow.webContents.send('overlay-show');
  }
}

/**
 * Hide the overlay
 */
function hideOverlay() {
  if (mainWindow) {
    mainWindow.hide();
    isOverlayVisible = false;
    mainWindow.webContents.send('overlay-hide');
  }
}

/**
 * App event: when app is ready
 */
app.on('ready', () => {
  console.log('[APP] Electron app is ready');
  
  createOverlayWindow();
  registerHotkeys();
  initWebSocket();
});

/**
 * App event: when all windows are closed (Windows/Linux)
 */
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

/**
 * App event: when app is activated (macOS)
 */
app.on('activate', () => {
  if (mainWindow === null) {
    createOverlayWindow();
  }
});

/**
 * App event: before quit
 */
app.on('before-quit', () => {
  console.log('[APP] Cleaning up...');
  globalShortcut.unregisterAll();
  if (ws) {
    ws.close();
  }
});

/**
 * IPC Handler: Send message to Python backend
 */
ipcMain.on('send-to-backend', (event, message) => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(message));
  } else {
    console.warn('[IPC] WebSocket not connected, cannot send:', message);
  }
});

/**
 * IPC Handler: Hide overlay from renderer
 */
ipcMain.on('hide-overlay', () => {
  hideOverlay();
});

/**
 * IPC Handler: Show overlay from renderer
 */
ipcMain.on('show-overlay', () => {
  showOverlay();
});

/**
 * IPC Handler: Get viewport size (for coordinate normalization)
 */
ipcMain.handle('get-viewport', () => {
  if (mainWindow) {
    const { width, height } = mainWindow.getBounds();
    return { width, height };
  }
  return { width: 1920, height: 1080 };
});

console.log('[CLEVRR OVERLAY] Main process initialized');
