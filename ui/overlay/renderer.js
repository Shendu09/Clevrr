/**
 * Renderer — Overlay Canvas Rendering & Input Handling
 * 
 * Features:
 * - Canvas initialization and drawing
 * - Input bar interaction
 * - Element tracking (boxes, text, dots)
 * - Commands from Python backend
 * - Smooth animations and fading
 * - Glow effects and shadows
 * - Pulse animations for loading
 */

const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');
const inputContainer = document.getElementById('input-container');
const inputField = document.getElementById('input-field');
const statusIndicator = document.getElementById('status-indicator');
const statusBubble = document.getElementById('status-bubble');
let isVisible = false;
let isConnected = false;

// Animation state
let animationFrame = null;
let currentTime = 0;

// Element registry (track drawn items with animation state)
const elements = {
  boxes: new Map(),      // id -> {x, y, width, height, stroke, strokeWidth, opacity, ...}
  texts: new Map(),      // id -> {x, y, text, fontSize, opacity, ...}
  dots: new Map(),       // id -> {x, y, radius, color, opacity, ...}
  animations: new Map(), // id -> {type, startTime, duration, ...}
};

/**
 * Initialize canvas to fullscreen
 */
function initCanvas() {
  const { width, height } = window.screen;
  canvas.width = width;
  canvas.height = height;
  
  console.log('[RENDERER] Canvas initialized:', width, 'x', height);
  
  // Start animation loop
  startAnimationLoop();
}

/**
 * Start continuous animation loop
 */
function startAnimationLoop() {
  currentTime = Date.now();
  
  function animate() {
    currentTime = Date.now();
    redraw();
    animationFrame = requestAnimationFrame(animate);
  }
  
  animate();
}

/**
 * Easing functions for animations
 */
const easing = {
  linear: t => t,
  easeIn: t => t * t,
  easeOut: t => 1 - (1 - t) * (1 - t),
  easeInOut: t => t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t,
  easeInQuad: t => t * t,
  easeOutQuad: t => t * (2 - t),
  easeInCubic: t => t * t * t,
  easeOutCubic: t => (--t) * t * t + 1,
  easeInExp: t => t === 0 ? 0 : Math.pow(2, 10 * (t - 1)),
  easeOutExp: t => t === 1 ? 1 : 1 - Math.pow(2, -10 * t),
  elastic: t => {
    const c5 = (2 * Math.PI) / 4.5;
    return t === 0 ? 0 : t === 1 ? 1 : Math.pow(2, -10 * t) * Math.sin((t * 40 - 3) * c5) + 1;
  },
};

/**
 * Calculate animation progress (0-1)
 */
function getAnimationProgress(startTime, duration) {
  const elapsed = Date.now() - startTime;
  return Math.min(elapsed / duration, 1);
}

/**
 * Redraw all elements on canvas
 */
function redraw() {
  // Clear canvas
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  
  // Draw boxes with animations
  for (const [id, box] of elements.boxes) {
    const animatedBox = applyAnimation(box, id, 'box');
    if (animatedBox) drawBox(animatedBox);
  }
  
  // Draw dots with animations
  for (const [id, dot] of elements.dots) {
    const animatedDot = applyAnimation(dot, id, 'dot');
    if (animatedDot) drawDot(animatedDot);
  }
  
  // Draw text with animations
  for (const [id, text] of elements.texts) {
    const animatedText = applyAnimation(text, id, 'text');
    if (animatedText) drawText(animatedText);
  }
}

/**
 * Apply animations to element
 */
function applyAnimation(element, id, type) {
  const anim = elements.animations.get(id);
  if (!anim) return element;
  
  const progress = getAnimationProgress(anim.startTime, anim.duration);
  if (progress >= 1) {
    // Animation finished
    elements.animations.delete(id);
    return element;
  }
  
  const eased = easing[anim.easingType || 'easeOut'](progress);
  
  // Apply animation effect
  switch (anim.animationType) {
    case 'fade-in':
      return { ...element, opacity: eased };
    
    case 'fade-out':
      return { ...element, opacity: 1 - eased };
    
    case 'pulse':
      const pulse = 0.5 + 0.5 * Math.sin(progress * Math.PI * 2);
      return { ...element, opacity: element.opacity * pulse };
    
    case 'glow':
      return { ...element, glow: eased * (anim.glowIntensity || 10) };
    
    case 'scale':
      return {
        ...element,
        opacity: element.opacity * eased,
        scale: eased
      };
    
    default:
      return element;
  }
}

/**
 * Draw a box on canvas with glow
 */
function drawBox(box) {
  const {
    x, y, width, height,
    stroke = '#ff4d4d',
    strokeWidth = 3,
    opacity = 1,
    glow = 0,
    scale = 1,
  } = box;
  
  // Apply scale transformation
  if (scale !== 1) {
    const centerX = x + width / 2;
    const centerY = y + height / 2;
    ctx.translate(centerX, centerY);
    ctx.scale(scale, scale);
    ctx.translate(-centerX, -centerY);
  }
  
  ctx.save();
  ctx.globalAlpha = opacity;
  
  // Draw glow if present
  if (glow > 0) {
    ctx.shadowColor = stroke;
    ctx.shadowBlur = glow;
    ctx.shadowOffsetX = 0;
    ctx.shadowOffsetY = 0;
  }
  
  ctx.strokeStyle = stroke;
  ctx.lineWidth = strokeWidth;
  ctx.strokeRect(x, y, width, height);
  
  ctx.restore();
  
  if (scale !== 1) ctx.resetTransform();
}

/**
 * Draw text on canvas with glow
 */
function drawText(text) {
  const {
    x, y, text: content,
    fontSize = 16,
    fontFamily = 'Helvetica',
    color = 'white',
    align = 'left',
    baseline = 'top',
    opacity = 1,
    glow = 0,
    scale = 1,
  } = text;
  
  ctx.save();
  ctx.globalAlpha = opacity;
  ctx.fillStyle = color;
  ctx.font = `${fontSize}px ${fontFamily}`;
  ctx.textAlign = align;
  ctx.textBaseline = baseline;
  
  // Draw glow if present
  if (glow > 0) {
    ctx.shadowColor = color;
    ctx.shadowBlur = glow;
  }
  
  ctx.fillText(content, x, y);
  ctx.restore();
}

/**
 * Draw a dot on canvas with glow
 */
/**
 * Draw a dot on canvas with glow
 */
function drawDot(dot) {
  const { x, y, radius = 6, color = '#00ffcc', opacity = 1, glow = 0 } = dot;
  
  ctx.save();
  ctx.globalAlpha = opacity;
  
  // Draw glow if present
  if (glow > 0) {
    ctx.shadowColor = color;
    ctx.shadowBlur = glow;
  }
  
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.arc(x, y, radius, 0, 2 * Math.PI);
  ctx.fill();
  
  ctx.restore();
}

/**
 * Start animation on element
 */
function animateElement(id, animationType, duration = 500, easingType = 'easeOut', options = {}) {
  elements.animations.set(id, {
    animationType,
    startTime: Date.now(),
    duration,
    easingType,
    ...options
  });
}

/**
 * Fade in element over duration
 */
function fadeIn(id, type, duration = 300) {
  animateElement(id, 'fade-in', duration, 'easeIn');
}

/**
 * Fade out and remove element
 */
function fadeOut(id, type, duration = 300) {
  animateElement(id, 'fade-out', duration, 'easeOut');
  
  // Remove after animation completes
  setTimeout(() => {
    if (type === 'box') elements.boxes.delete(id);
    else if (type === 'text') elements.texts.delete(id);
    else if (type === 'dot') elements.dots.delete(id);
  }, duration);
}

/**
 * Pulse animation (loading indicator)
 */
function pulse(id, duration = 1000) {
  animateElement(id, 'pulse', duration, 'linear');
}

/**
 * Glow animation (attention drawing)
 */
function glow(id, duration = 600, intensity = 10) {
  animateElement(id, 'glow', duration, 'easeInOut', { glowIntensity: intensity });
}

/**
 * Scale animation (pop in effect)
 */
function popIn(id, duration = 400) {
  animateElement(id, 'scale', duration, 'easeOutCubic');
}

/**
 * Handle backend commands
 */
function handleBackendCommand(cmd) {
  const { command, id, ...args } = cmd;
  
  switch (command) {
    case 'draw_box':
      elements.boxes.set(id, { opacity: 0, ...args });
      fadeIn(id, 'box', 200);
      popIn(id, 300);
      console.log('[RENDERER] Drawn box:', id);
      break;
    
    case 'destroy_box':
      fadeOut(id, 'box', 300);
      console.log('[RENDERER] Destroyed box:', id);
      break;
    
    case 'draw_text':
      elements.texts.set(id, { opacity: 0, ...args });
      fadeIn(id, 'text', 200);
      console.log('[RENDERER] Drawn text:', id);
      break;
    
    case 'destroy_text':
      fadeOut(id, 'text', 300);
      console.log('[RENDERER] Destroyed text:', id);
      break;
    
    case 'draw_dot':
      elements.dots.set(id, { opacity: 0, ...args });
      fadeIn(id, 'dot', 200);
      popIn(id, 300);
      console.log('[RENDERER] Drawn dot:', id);
      break;
    
    case 'destroy_dot':
      fadeOut(id, 'dot', 300);
      console.log('[RENDERER] Destroyed dot:', id);
      break;
    
    case 'clear':
      // Fade out all elements
      for (const id of elements.boxes.keys()) fadeOut(id, 'box', 200);
      for (const id of elements.texts.keys()) fadeOut(id, 'text', 200);
      for (const id of elements.dots.keys()) fadeOut(id, 'dot', 200);
      console.log('[RENDERER] Cleared all elements');
      break;
    
    case 'status':
      showStatus(args.text, args.color || 'white', args.duration);
      break;
    
    case 'animate':
      // Dynamic animation command
      animateElement(args.elementId, args.type, args.duration, args.easing, args.options);
      break;
    
    default:
      console.warn('[RENDERER] Unknown command:', command);
  }
}

/**
 * Show status message bubble with animation
 */
function showStatus(text, color = 'white', duration = 2000) {
  statusBubble.textContent = text;
  statusBubble.style.color = color;
  
  // Fade in
  statusBubble.style.opacity = '0';
  statusBubble.classList.add('visible');
  
  setTimeout(() => {
    statusBubble.style.opacity = '1';
    statusBubble.style.transition = 'opacity 0.3s ease-in';
  }, 10);
  
  // Fade out
  setTimeout(() => {
    statusBubble.style.opacity = '0';
    statusBubble.style.transition = 'opacity 0.3s ease-out';
    
    setTimeout(() => {
      statusBubble.classList.remove('visible');
      statusBubble.style.transition = 'none';
    }, 300);
  }, duration);
}

/**
 * Handle input submission
 */
function handleInputSubmit() {
  const query = inputField.value.trim();
  if (!query) return;
  
  console.log('[INPUT] Submitted:', query);
  
  // Send to backend
  window.clevrr.sendToBackend({
    type: 'query',
    query: query,
    timestamp: Date.now(),
  });
  
  // Show executing status
  showStatus('⚙Executing...', '#4fc3f7');
  
  // Clear input
  inputField.value = '';
  
  // Hide after submission (optional - can keep visible)
  // window.clevrr.hideOverlay();
}

/**
 * Handle input field events
 */
function initInputHandlers() {
  // Submit on Enter
  inputField.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      handleInputSubmit();
    }
    // Hide on Escape
    else if (e.key === 'Escape') {
      window.clevrr.hideOverlay();
    }
  });
  
  // Auto-focus when container is shown
  window.clevrr.onOverlayShow(() => {
    isVisible = true;
    inputContainer.classList.add('visible');
    inputField.focus();
    redraw(); // Redraw in case backend sent updates while hidden
  });
  
  // Clear and hide input when overlay hides
  window.clevrr.onOverlayHide(() => {
    isVisible = false;
    inputContainer.classList.remove('visible');
    inputField.value = '';
  });
}

/**
 * Initialize backend communication
 */
function initBackendConnection() {
  // Listen for messages from backend
  window.clevrr.onBackendMessage((message) => {
    handleBackendCommand(message);
  });
  
  // Listen for connected event
  window.clevrr.onBackendConnected(() => {
    console.log('[CONNECTION] Backend connected');
    isConnected = true;
    statusIndicator.classList.add('connected');
    showStatus('Backend connected', '#4caf50');
  });
}

/**
 * Initialize overlay
 */
function initOverlay() {
  console.log('[OVERLAY] Initializing...');
  
  initCanvas();
  initInputHandlers();
  initBackendConnection();
  
  // Hide by default
  window.clevrr.hideOverlay();
  
  console.log('[OVERLAY] Ready');
}

/**
 * Main
 */
document.addEventListener('DOMContentLoaded', initOverlay);

// Handle window resize (in case user changes resolution)
window.addEventListener('resize', () => {
  const { width, height } = window.screen;
  canvas.width = width;
  canvas.height = height;
  redraw();
  console.log('[RENDERER] Resized to:', width, 'x', height);
});
