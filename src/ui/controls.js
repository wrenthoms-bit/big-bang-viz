import { DURATION, STAGES } from '../timeline.js';

export function createControls({
  onPlayPause,
  onSeek,
  onToggleLabels,
  onStartRecord,
  onCancelRecord
}) {
  const btnPlayPause = document.getElementById('btn-play-pause');
  const iconPlay = document.getElementById('icon-play');
  const iconPause = document.getElementById('icon-pause');
  const labelPlayPause = document.getElementById('label-play-pause');

  const scrubSlider = document.getElementById('scrub-slider');
  const markersWrap = document.getElementById('stage-markers');

  const btnLabels = document.getElementById('btn-labels');
  const labelsState = document.getElementById('labels-state');

  const btnRecord = document.getElementById('btn-record');
  const recordBtnText = document.getElementById('record-btn-text');
  const btnCancelRecord = document.getElementById('btn-cancel-record');
  const recordProgressWrap = document.getElementById('record-progress-wrap');
  const recordProgressFill = document.getElementById('record-progress-fill');
  const recordStatusText = document.getElementById('record-status-text');

  // Populate 6 clickable stage markers above the scrub track
  STAGES.forEach((stage, i) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'stage-marker-btn';
    const pct = (stage.start / DURATION) * 100;
    btn.style.left = `${pct}%`;
    btn.title = `Jump to Stage ${i + 1}: ${stage.title} (${stage.start}s)`;

    const dot = document.createElement('span');
    dot.className = 'stage-marker-dot';
    dot.style.background = stage.markerColor;

    const text = document.createElement('span');
    text.className = 'stage-marker-label';
    text.textContent = `${stage.start}s`;

    btn.appendChild(dot);
    btn.appendChild(text);
    btn.addEventListener('click', () => {
      const targetU = i === 0 ? 0.0 : stage.start + 0.30;
      onSeek(targetU, false);
    });
    markersWrap.appendChild(btn);
  });

  btnPlayPause.addEventListener('click', onPlayPause);

  scrubSlider.addEventListener('input', (e) => {
    const val = parseFloat(e.target.value);
    onSeek(val, false);
  });

  btnLabels.addEventListener('click', onToggleLabels);
  btnRecord.addEventListener('click', onStartRecord);
  btnCancelRecord.addEventListener('click', onCancelRecord);

  window.addEventListener('keydown', (e) => {
    if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) {
      if (e.code !== 'Space') return;
    }
    if (e.code === 'Space') {
      e.preventDefault();
      onPlayPause();
    } else if (e.key === 'l' || e.key === 'L') {
      onToggleLabels();
    }
  });

  function setPlaying(isPlaying) {
    iconPlay.classList.toggle('hidden', isPlaying);
    iconPause.classList.toggle('hidden', !isPlaying);
    labelPlayPause.textContent = isPlaying ? 'Pause' : 'Play';
  }

  function setLabelsVisible(visible) {
    btnLabels.classList.toggle('active', visible);
    labelsState.textContent = visible ? 'ON' : 'OFF';
  }

  function setRecordingState(recording, currentFrame = 0, totalFrames = 1200, statusOverride = '') {
    btnPlayPause.disabled = recording;
    scrubSlider.disabled = recording;
    btnRecord.disabled = recording;
    btnCancelRecord.classList.toggle('hidden', !recording);
    recordProgressWrap.classList.toggle('hidden', !recording);
    recordBtnText.textContent = recording ? 'Recording...' : 'Record 1080p60';

    if (recording) {
      const pct = Math.min(100, (currentFrame / Math.max(1, totalFrames)) * 100);
      recordProgressFill.style.width = `${pct.toFixed(1)}%`;
      recordStatusText.textContent = statusOverride || `Frame ${currentFrame} / ${totalFrames}`;
    } else {
      recordProgressFill.style.width = '0%';
    }
  }

  return {
    setPlaying,
    setLabelsVisible,
    setRecordingState
  };
}
