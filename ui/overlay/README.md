# Clevrr Overlay — Electron Transparent UI

## Overview

The Clevrr Overlay is a transparent Electron application that sits on top of your screen, providing:

- **Hotkey-driven activation** (Win+Shift+Space or Cmd+Shift+Space)
- **Real-time visual annotations** (bounding boxes, text labels, highlighting)
- **Direct command input** without menu navigation
- **100% local processing** via WebSocket with Python backend

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Electron Overlay (Transparent)               │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Canvas (for drawing boxes, text, dots)                  │  │
│  │  Input Bar (bottom-center)                               │  │
│  │  Status Bubble (status messages)                         │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
         ↕ WebSocket (ws://localhost:9999)
     ┌────────────────────────────────────────┐
     │   Python Backend (server.py)           │
     │  ┌──────────────────────────────────┐  │
     │  │  RouterService                   │  │
     │  │  ├─ Route query                  │  │
     │  │  ├─ Agent dispatch               │  │
     │  │  └─ Result handling              │  │
     │  └──────────────────────────────────┘  │
     └────────────────────────────────────────┘
```

## Setup

### 1. Install Electron & Dependencies

```bash
cd ui/overlay
npm install
```

### 2. Add to Main Python App

In `main.py`, add:

```python
from ui.overlay.server import get_overlay_server

# When starting the app:
overlay_server = get_overlay_server()
overlay_server.set_router_service(router_service)
overlay_server.start_background()

# Launch Electron:
import subprocess
subprocess.Popen(['npm', 'start'], cwd='ui/overlay')
```

### 3. Run

```bash
python main.py --ui overlay
```

## Files

| File | Purpose |
|------|---------|
| `package.json` | NPM dependencies (Electron, WebSocket) |
| `main.js` | Electron main process, hotkey registration |
| `preload.js` | IPC security bridge |
| `renderer.js` | Canvas rendering, input handling |
| `index.html` | Overlay HTML structure |
| `server.py` | Python WebSocket server |

## Hotkeys

| Hotkey | Action |
|--------|--------|
| Win+Shift+Space | Toggle overlay visibility |
| Enter (in input) | Submit query |
| Escape (in input) | Hide overlay |

## Commands (Python → Electron)

The Python backend sends drawing commands via WebSocket:

```json
{
  "command": "draw_box",
  "id": "box_1",
  "x": 100,
  "y": 200,
  "width": 300,
  "height": 150,
  "stroke": "#ff4d4d",
  "strokeWidth": 3
}
```

### Available Commands

- `draw_box` — Draw a rectangle
- `destroy_box` — Remove a box
- `draw_text` — Draw text
- `destroy_text` — Remove text
- `draw_dot` — Draw a dot/circle
- `destroy_dot` — Remove a dot
- `clear` — Clear all drawings
- `status` — Show a status message

## Debugging

### Check Electron is running
```bash
ps aux | grep electron
```

### Check WebSocket connection
The status indicator (dot) in the input bar shows connection status:
- 🔴 Red: Disconnected
- 🟢 Green: Connected

### View Electron DevTools
Modify `main.js` and uncommenta:
```javascript
mainWindow.webContents.openDevTools();
```

Then run:
```bash
npm run dev
```

## Integration with Clevrr

The overlay integrates seamlessly with the existing Clevrr systems:

1. **Router** routes queries to appropriate agents
2. **ActionQueue** sequences visual feedback (timing drawing commands)
3. **Agents** execute tasks and optionally send visual feedback

Example flow:
```
User: "Open Notepad"
  ↓
Router: invokes os_control
  ↓
Agent: launches app, gets window bounds
  ↓
ActionQueue: schedule draw_box(bounds) at t=0, destroy at t=3
  ↓
Electron: draws bounding box, shows animated label, fades out
```

## Performance

- **Hotkey response**: <100ms
- **Rendering**: 60fps canvas
- **WebSocket latency**: <10ms (local)
- **Overlay memory**: ~50MB
- **CPU**: <2% idle, <10% during rendering

## Future Enhancements

- [ ] Animation support (fade, slide, pulse)
- [ ] Multi-element grouping
- [ ] Voice feedback integration
- [ ] Screenshot comparison
- [ ] Mouse tracking display
- [ ] Keyboard input visualization
- [ ] Gesture recognition
- [ ] AR-style pointer effects

