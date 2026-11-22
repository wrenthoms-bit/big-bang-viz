import {
  DURATION,
  STAGES,
  getPhysicalTime,
  getTemperature,
  getActiveStage,
  smoothstep
} from '../timeline.js';

export function createHud() {
  const clockEl = document.getElementById('clock-readout');
  const tempEl = document.getElementById('temp-readout');
  const captionEl = document.getElementById('concept-caption');
  const stageLabelEl = document.getElementById('stage-label');
  const stageIndexPillEl = document.getElementById('stage-index-pill');
  const stageEpochEl = document.getElementById('stage-epoch');
  const stageTitleEl = document.getElementById('stage-title');
  const stageSubtitleEl = document.getElementById('stage-subtitle');
  const timelineClockEl = document.getElementById('timeline-clock');
  const scrubSliderEl = document.getElementById('scrub-slider');
  const fpsBadgeEl = document.getElementById('fps-badge');

  let lastStageIdx = -1;
  let lastSubtitle = '';
  let lastStateSnapshot = {};

  function update(u, labelsVisible, fps, isRecording) {
    const physTime = getPhysicalTime(u);
    const temp = getTemperature(u);
    const active = getActiveStage(u);

    clockEl.innerHTML = physTime.formattedHTML;
    tempEl.innerHTML = temp.formattedHTML;
    timelineClockEl.textContent = `${u.toFixed(1).padStart(4, '0')}s / ${DURATION.toFixed(1)}s`;

    if (document.activeElement !== scrubSliderEl) {
      scrubSliderEl.value = u.toFixed(2);
    }

    // Core concept caption shown at start (u = 0..4.5s) when labels are enabled
    const captionFade = 1.0 - smoothstep(3.8, 4.6, u);
    const captionOpacity = labelsVisible ? captionFade : 0.0;
    captionEl.style.opacity = captionOpacity.toFixed(3);
    captionEl.style.visibility = captionOpacity > 0.01 ? 'visible' : 'hidden';

    // Documentary stage label
    if (active.stageIndex !== lastStageIdx) {
      lastStageIdx = active.stageIndex;
      stageIndexPillEl.textContent = `STAGE ${active.stageIndex + 1} / ${STAGES.length}`;
      stageEpochEl.innerHTML = active.stage.epochHTML;
      stageTitleEl.textContent = active.stage.title;
    }
    if (active.subtitle !== lastSubtitle) {
      lastSubtitle = active.subtitle;
      stageSubtitleEl.textContent = active.subtitle;
    }

    const labelOpacity = labelsVisible ? active.opacity : 0.0;
    stageLabelEl.style.opacity = labelOpacity.toFixed(3);
    stageLabelEl.style.visibility = labelOpacity > 0.01 ? 'visible' : 'hidden';

    // Update marker active styling
    const markers = document.querySelectorAll('.stage-marker-btn');
    markers.forEach((btn, idx) => {
      btn.classList.toggle('active', idx === active.stageIndex);
    });

    if (isRecording) {
      fpsBadgeEl.classList.add('hidden');
    } else {
      fpsBadgeEl.classList.remove('hidden');
      if (fps > 0) {
        fpsBadgeEl.textContent = `${Math.round(fps)} FPS`;
      }
    }

    lastStateSnapshot = {
      u,
      stageIndex: active.stageIndex,
      stageId: active.stage.id,
      stageTitle: active.stage.title,
      stageEpoch: active.stage.epoch,
      stageSubtitle: active.subtitle,
      labelOpacity,
      timeText: physTime.formattedPlain,
      tempText: temp.formattedPlain,
      labelsVisible
    };
  }

  function getSnapshot() {
    return lastStateSnapshot;
  }

  return { update, getSnapshot };
}
