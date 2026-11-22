import './style.css';
import { DURATION, clamp } from './timeline.js';
import { createBigBangScene } from './scene/BigBangScene.js';
import { createHud } from './ui/hud.js';
import { createControls } from './ui/controls.js';
import { createWebMRecorder, getRecorderSupport } from './recorder.js';

const canvas = document.getElementById('gl-canvas');
const scene = createBigBangScene(canvas);
const hud = createHud();
const recorder = createWebMRecorder(scene);

let u = 0.0;
let isPlaying = true;
let labelsVisible = true;
let isRecording = false;

// Rolling FPS tracker over last 60 frames
const frameTimes = [];
let lastNow = performance.now();
let measuredFps = 60;
let avgFrameMs = 16.67;

const controls = createControls({
  onPlayPause: () => {
    if (isRecording) return;
    isPlaying = !isPlaying;
    controls.setPlaying(isPlaying);
    lastNow = performance.now();
  },
  onSeek: (targetU, resumePlay = false) => {
    if (isRecording) return;
    u = clamp(targetU, 0, DURATION);
    isPlaying = resumePlay;
    controls.setPlaying(isPlaying);
    renderOnce();
  },
  onToggleLabels: () => {
    labelsVisible = !labelsVisible;
    controls.setLabelsVisible(labelsVisible);
    renderOnce();
  },
  onStartRecord: async () => {
    if (isRecording) return;
    const wasPlaying = isPlaying;
    const prevU = u;
    isPlaying = false;
    isRecording = true;
    controls.setPlaying(false);
    controls.setRecordingState(true, 0, recorder.totalFrames);

    try {
      await recorder.record({
        labelsVisible,
        onProgress: (frame, total, statusText) => {
          controls.setRecordingState(true, frame, total, statusText);
        }
      });
    } catch (err) {
      console.error('Recording failed:', err);
    } finally {
      isRecording = false;
      controls.setRecordingState(false);
      u = prevU;
      isPlaying = wasPlaying;
      controls.setPlaying(isPlaying);
      lastNow = performance.now();
      renderOnce();
    }
  },
  onCancelRecord: () => {
    recorder.cancel();
  }
});

controls.setPlaying(isPlaying);
controls.setLabelsVisible(labelsVisible);

window.addEventListener('resize', () => {
  if (!isRecording) {
    scene.resizeToViewport();
    renderOnce();
  }
});

function renderOnce() {
  scene.renderAt(u);
  hud.update(u, labelsVisible, measuredFps, isRecording);
}

function tick(now) {
  requestAnimationFrame(tick);

  const dtMs = now - lastNow;
  lastNow = now;

  if (dtMs > 0 && dtMs < 500) {
    frameTimes.push(dtMs);
    if (frameTimes.length > 60) frameTimes.shift();
    const sum = frameTimes.reduce((a, b) => a + b, 0);
    avgFrameMs = sum / frameTimes.length;
    measuredFps = 1000 / Math.max(1, avgFrameMs);
  }

  if (!isRecording) {
    if (isPlaying) {
      const dt = Math.min(0.05, Math.max(0, dtMs * 0.001));
      u = (u + dt) % DURATION;
    }
    renderOnce();
  }
}

// Expose deterministic inspection API for browser verification
window.__BIG_BANG_DEBUG__ = {
  seek(targetU) {
    isPlaying = false;
    controls.setPlaying(false);
    u = clamp(targetU, 0, DURATION);
    renderOnce();
    return this.getState();
  },
  play() {
    isPlaying = true;
    controls.setPlaying(true);
    lastNow = performance.now();
  },
  pause() {
    isPlaying = false;
    controls.setPlaying(false);
    renderOnce();
  },
  setLabels(visible) {
    labelsVisible = Boolean(visible);
    controls.setLabelsVisible(labelsVisible);
    renderOnce();
  },
  getState() {
    return {
      ...hud.getSnapshot(),
      isPlaying,
      fps: Number(measuredFps.toFixed(1)),
      avgFrameMs: Number(avgFrameMs.toFixed(2)),
      recording: isRecording
    };
  },
  getRecorderSupport
};

renderOnce();
requestAnimationFrame(tick);
