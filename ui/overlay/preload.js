/**
 * Preload Script — Secure IPC Bridge
 * 
 * Provides safe API for renderer to communicate with main process.
 * Context isolation is enabled, so this is the only way to access
 * main process from the renderer.
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('clevrr', {
  /**
   * Send a message to the Python backend via WebSocket
   * @param {Object} message - Message to send
   */
  sendToBackend: (message) => {
    ipcRenderer.send('send-to-backend', message);
  },

  /**
   * Listen for messages from Python backend
   * @param {Function} callback - Function to call when message arrives
   */
  onBackendMessage: (callback) => {
    ipcRenderer.on('backend-message', (event, data) => {
      callback(JSON.parse(data));
    });
  },

  /**
   * Listen for backend connection event
   * @param {Function} callback - Function to call when connected
   */
  onBackendConnected: (callback) => {
    ipcRenderer.on('backend-connected', callback);
  },

  /**
   * Listen for overlay show event
   * @param {Function} callback - Function to call when showing
   */
  onOverlayShow: (callback) => {
    ipcRenderer.on('overlay-show', callback);
  },

  /**
   * Listen for overlay hide event
   * @param {Function} callback - Function to call when hiding
   */
  onOverlayHide: (callback) => {
    ipcRenderer.on('overlay-hide', callback);
  },

  /**
   * Hide the overlay
   */
  hideOverlay: () => {
    ipcRenderer.send('hide-overlay');
  },

  /**
   * Show the overlay
   */
  showOverlay: () => {
    ipcRenderer.send('show-overlay');
  },

  /**
   * Get viewport dimensions for coordinate mapping
   * @returns {Promise<{width: number, height: number}>}
   */
  getViewport: () => {
    return ipcRenderer.invoke('get-viewport');
  },
});
