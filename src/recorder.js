import { Muxer, ArrayBufferTarget } from 'webm-muxer';
import { DURATION } from './timeline.js';
import { drawHudOnCanvas } from './ui/hudCanvasRenderer.js';

const WIDTH = 1920;
const HEIGHT = 1080;
const FPS = 60;
const TOTAL_FRAMES = Math.round(DURATION * FPS); // 1200 frames

function nextTick() {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, 1000);
}

async function pickSupportedVideoCodec() {
  if (typeof VideoEncoder === 'undefined') return null;
  const candidates = [
    { webCodecs: 'vp09.00.41.08', muxer: 'V_VP9' },
    { webCodecs: 'vp09.00.10.08', muxer: 'V_VP9' },
    { webCodecs: 'vp8', muxer: 'V_VP8' }
  ];
  for (const c of candidates) {
    try {
      const res = await VideoEncoder.isConfigSupported({
        codec: c.webCodecs,
        width: WIDTH,
        height: HEIGHT,
        bitrate: 14_000_000,
        framerate: FPS
      });
      if (res.supported) return c;
    } catch {
      // Try next codec candidate
    }
  }
  return null;
}

export function getRecorderSupport() {
  const hasWebCodecs = typeof VideoEncoder !== 'undefined' && typeof VideoFrame !== 'undefined';
  const hasMediaRecorder =
    typeof MediaRecorder !== 'undefined' &&
    typeof HTMLCanvasElement.prototype.captureStream === 'function';
  return {
    webCodecs: hasWebCodecs,
    mediaRecorder: hasMediaRecorder
  };
}

export function createWebMRecorder(scene) {
  let cancelled = false;

  function cancel() {
    cancelled = true;
  }

  async function record({ labelsVisible, onProgress }) {
    cancelled = false;

    const compCanvas = document.createElement('canvas');
    compCanvas.width = WIDTH;
    compCanvas.height = HEIGHT;
    const ctx = compCanvas.getContext('2d', { alpha: false });

    scene.setFixedResolution(WIDTH, HEIGHT);

    try {
      const codec = await pickSupportedVideoCodec();
      if (codec) {
        return await recordWithWebCodecs({
          codec,
          compCanvas,
          ctx,
          labelsVisible,
          onProgress
        });
      }
      return await recordWithMediaRecorder({
        compCanvas,
        ctx,
        labelsVisible,
        onProgress
      });
    } finally {
      scene.restoreViewportResolution();
    }
  }

  async function recordWithWebCodecs({ codec, compCanvas, ctx, labelsVisible, onProgress }) {
    const target = new ArrayBufferTarget();
    const muxer = new Muxer({
      target,
      video: {
        codec: codec.muxer,
        width: WIDTH,
        height: HEIGHT,
        frameRate: FPS
      },
      firstTimestampBehavior: 'offset'
    });

    let encoderError = null;
    const encoder = new VideoEncoder({
      output: (chunk, meta) => muxer.addVideoChunk(chunk, meta),
      error: (err) => {
        encoderError = err;
      }
    });

    encoder.configure({
      codec: codec.webCodecs,
      width: WIDTH,
      height: HEIGHT,
      bitrate: 14_000_000,
      framerate: FPS
    });

    const frameDurationUs = Math.round(1_000_000 / FPS);

    for (let frame = 0; frame < TOTAL_FRAMES; frame++) {
      if (cancelled || encoderError) break;

      const u = frame / FPS;
      scene.renderAt(u);

      ctx.drawImage(scene.renderer.domElement, 0, 0, WIDTH, HEIGHT);
      drawHudOnCanvas(ctx, WIDTH, HEIGHT, u, labelsVisible);

      const timestampUs = Math.round(frame * (1_000_000 / FPS));
      const videoFrame = new VideoFrame(compCanvas, {
        timestamp: timestampUs,
        duration: frameDurationUs
      });

      encoder.encode(videoFrame, { keyFrame: frame % 120 === 0 });
      videoFrame.close();

      onProgress(frame + 1, TOTAL_FRAMES);

      // Keep UI responsive and avoid overflowing encoder queue
      if (encoder.encodeQueueSize > 8 || frame % 3 === 0) {
        await nextTick();
      }
    }

    if (cancelled) {
      try {
        encoder.close();
      } catch {
        // ignore close errors
      }
      return { completed: false, cancelled: true };
    }

    if (encoderError) {
      throw encoderError;
    }

    onProgress(TOTAL_FRAMES, TOTAL_FRAMES, 'Finalizing WebM...');
    await encoder.flush();
    encoder.close();
    muxer.finalize();

    const blob = new Blob([target.buffer], { type: 'video/webm' });
    downloadBlob(blob, 'big-bang-first-3-seconds-1080p60.webm');
    return { completed: true, cancelled: false, bytes: blob.size, engine: 'WebCodecs' };
  }

  async function recordWithMediaRecorder({ compCanvas, ctx, labelsVisible, onProgress }) {
    const stream = compCanvas.captureStream(0);
    const track = stream.getVideoTracks()[0];
    const mimeType = MediaRecorder.isTypeSupported('video/webm;codecs=vp9')
      ? 'video/webm;codecs=vp9'
      : 'video/webm';

    const chunks = [];
    const mediaRecorder = new MediaRecorder(stream, {
      mimeType,
      videoBitsPerSecond: 14_000_000
    });

    mediaRecorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) chunks.push(e.data);
    };

    const stopped = new Promise((resolve) => {
      mediaRecorder.onstop = resolve;
    });

    mediaRecorder.start(250);

    for (let frame = 0; frame < TOTAL_FRAMES; frame++) {
      if (cancelled) break;
      const u = frame / FPS;
      scene.renderAt(u);
      ctx.drawImage(scene.renderer.domElement, 0, 0, WIDTH, HEIGHT);
      drawHudOnCanvas(ctx, WIDTH, HEIGHT, u, labelsVisible);

      if (track && typeof track.requestFrame === 'function') {
        track.requestFrame();
      }

      onProgress(frame + 1, TOTAL_FRAMES);
      await new Promise((r) => setTimeout(r, 16));
    }

    mediaRecorder.stop();
    await stopped;
    stream.getTracks().forEach((t) => t.stop());

    if (cancelled) {
      return { completed: false, cancelled: true };
    }

    const blob = new Blob(chunks, { type: mimeType });
    downloadBlob(blob, 'big-bang-first-3-seconds-1080p60.webm');
    return { completed: true, cancelled: false, bytes: blob.size, engine: 'MediaRecorder' };
  }

  return { record, cancel, totalFrames: TOTAL_FRAMES };
}
