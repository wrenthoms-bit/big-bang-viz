import * as THREE from 'three';

export const DURATION = 20.0;

export const STAGES = [
  {
    id: 'planck',
    index: 0,
    start: 0.0,
    end: 2.0,
    title: 'PLANCK ERA',
    shortLabel: 'Planck',
    epoch: '~10⁻⁴³ s',
    epochHTML: '~10<sup>&minus;43</sup> s',
    subtitle: 'Physics unknown.',
    markerColor: '#dceeff'
  },
  {
    id: 'inflation',
    index: 1,
    start: 2.0,
    end: 6.0,
    title: 'INFLATION',
    shortLabel: 'Inflation',
    epoch: '10⁻³⁶ – 10⁻³² s',
    epochHTML: '10<sup>&minus;36</sup> &ndash; 10<sup>&minus;32</sup> s',
    subtitle: 'Space stretches exponentially; quantum ripples freeze in',
    markerColor: '#66d9ff'
  },
  {
    id: 'qgp',
    index: 2,
    start: 6.0,
    end: 11.0,
    title: 'QUARK–GLUON PLASMA',
    shortLabel: 'Quark–Gluon',
    epoch: '10⁻³² – ~10⁻⁶ s',
    epochHTML: '10<sup>&minus;32</sup> &ndash; ~10<sup>&minus;6</sup> s',
    subtitle: 'Turbulent quark streams and gluon energy filaments',
    markerColor: '#ff7043'
  },
  {
    id: 'hadrons',
    index: 3,
    start: 11.0,
    end: 14.0,
    title: 'PROTONS & NEUTRONS FORM',
    shortLabel: 'Protons/Neutrons',
    epoch: '~10⁻⁶ – 10⁻⁴ s',
    epochHTML: '~10<sup>&minus;6</sup> &ndash; 10<sup>&minus;4</sup> s',
    subtitle: 'Quarks snap together into luminous clusters of three',
    markerColor: '#ffc145'
  },
  {
    id: 'matter',
    index: 4,
    start: 14.0,
    end: 16.0,
    title: 'MATTER SURVIVES',
    shortLabel: 'Annihilation',
    epoch: '~10⁻⁴ s onward',
    epochHTML: '~10<sup>&minus;4</sup> s onward',
    subtitle: 'Annihilation flashes leave ~1 in a billion particles',
    markerColor: '#ffe0a3'
  },
  {
    id: 'neutrinos',
    index: 5,
    start: 16.0,
    end: 20.0,
    title: 'NEUTRINOS DECOUPLE',
    shortLabel: 'Neutrinos / Ripples',
    epoch: '~1 – 3 s',
    epochHTML: '~1 &ndash; 3 s',
    subtitle: 'Faint trails stream freely through cooling plasma',
    lateSubtitle: 'Cooling opaque plasma — faint density ripples, seeds of future galaxies',
    markerColor: '#ff8a50'
  }
];

export function clamp(x, min, max) {
  return Math.max(min, Math.min(max, x));
}

export function smoothstep(edge0, edge1, x) {
  const t = clamp((x - edge0) / (edge1 - edge0), 0, 1);
  return t * t * (3 - 2 * t);
}

export function lerp(a, b, t) {
  return a + (b - a) * t;
}

function samplePiecewiseSmooth(anchors, u) {
  const clamped = clamp(u, anchors[0][0], anchors[anchors.length - 1][0]);
  for (let i = 0; i < anchors.length - 1; i++) {
    const [u0, v0] = anchors[i];
    const [u1, v1] = anchors[i + 1];
    if (clamped <= u1 || i === anchors.length - 2) {
      const t = (clamped - u0) / Math.max(1e-6, u1 - u0);
      // Blend linear and smoothstep for gentle curvature without stalling at knots
      const s = t * t * (3 - 2 * t);
      return lerp(v0, v1, lerp(t, s, 0.45));
    }
  }
  return anchors[anchors.length - 1][1];
}

// Catmull-Rom spline over scalar control values at specific knot times
function sampleMonotonicSpline(knots, u) {
  const c = clamp(u, knots[0][0], knots[knots.length - 1][0]);
  for (let i = 0; i < knots.length - 1; i++) {
    const [t0, y0] = knots[i];
    const [t1, y1] = knots[i + 1];
    if (c <= t1 || i === knots.length - 2) {
      const localT = clamp((c - t0) / Math.max(1e-6, t1 - t0), 0, 1);
      const s = localT * localT * (3 - 2 * localT);
      return lerp(y0, y1, lerp(localT, s, 0.65));
    }
  }
  return knots[knots.length - 1][1];
}

const TIME_ANCHORS = [
  [0, -43.0],
  [2, -36.0],
  [6, -32.0],
  [11, -6.0],
  [14, -4.0],
  [16, 0.0],
  [20, Math.log10(3.0)]
];

const TEMP_ANCHORS = [
  [0, 32.15],
  [2, 28.0],
  [6, 26.0],
  [11, 12.48],
  [14, 11.18],
  [16, 10.0],
  [20, 9.76]
];

export function getPhysicalTime(u) {
  const log10Seconds = samplePiecewiseSmooth(TIME_ANCHORS, u);
  const seconds = Math.pow(10, log10Seconds);

  let formattedHTML;
  let formattedPlain;

  if (log10Seconds < -0.3) {
    let exp = Math.floor(log10Seconds);
    let mantissa = Math.pow(10, log10Seconds - exp);
    if (mantissa >= 9.95) {
      mantissa = 1.0;
      exp += 1;
    }
    const expStr = exp < 0 ? `&minus;${Math.abs(exp)}` : `${exp}`;
    const expPlain = `${exp}`;
    if (u <= 0.04) {
      formattedHTML = `10<sup>&minus;43</sup> s`;
      formattedPlain = `10^-43 s`;
    } else {
      const mStr = mantissa.toFixed(1);
      formattedHTML = `${mStr} &times; 10<sup>${expStr}</sup> s`;
      formattedPlain = `${mStr} x 10^${expPlain} s`;
    }
  } else {
    const valStr = seconds.toFixed(1);
    formattedHTML = `~${valStr} s`;
    formattedPlain = `~${valStr} s`;
  }

  return { log10Seconds, seconds, formattedHTML, formattedPlain };
}

export function getTemperature(u) {
  const log10Kelvin = samplePiecewiseSmooth(TEMP_ANCHORS, u);
  let exp = Math.floor(log10Kelvin);
  let mantissa = Math.pow(10, log10Kelvin - exp);
  if (mantissa >= 9.95) {
    mantissa = 1.0;
    exp += 1;
  }
  const mStr = mantissa.toFixed(1);
  return {
    log10Kelvin,
    formattedHTML: `~${mStr} &times; 10<sup>${exp}</sup> K`,
    formattedPlain: `~${mStr} x 10^${exp} K`
  };
}

export function getStageWeights(u) {
  const planck = 1.0 - smoothstep(1.55, 2.75, u);
  const inflation = smoothstep(1.55, 2.35, u) * (1.0 - smoothstep(5.45, 6.65, u));
  const qgp = smoothstep(5.45, 6.45, u) * (1.0 - smoothstep(10.35, 11.45, u));
  const hadrons = smoothstep(10.45, 11.25, u) * (1.0 - smoothstep(13.55, 14.35, u));
  const matter = smoothstep(13.55, 14.25, u) * (1.0 - smoothstep(15.65, 16.45, u));
  const neutrinos = smoothstep(15.65, 16.35, u) * (1.0 - smoothstep(18.6, 19.55, u));
  const ripples = smoothstep(17.2, 18.8, u);

  return { planck, inflation, qgp, hadrons, matter, neutrinos, ripples };
}

export function getActiveStage(u) {
  const cu = clamp(u, 0, DURATION);
  let idx = STAGES.length - 1;
  for (let i = 0; i < STAGES.length; i++) {
    if (cu < STAGES[i].end || i === STAGES.length - 1) {
      idx = i;
      break;
    }
  }
  const stage = STAGES[idx];

  // Keep Stage 1 immediately visible at u = 0, and Stage 6 visible through u = 20
  const fadeIn = idx === 0 ? 1.0 : smoothstep(stage.start, stage.start + 0.25, cu);
  const fadeOut = idx === STAGES.length - 1 ? 1.0 : 1.0 - smoothstep(stage.end - 0.25, stage.end, cu);
  const opacity = clamp(Math.min(fadeIn, fadeOut), 0, 1);

  let subtitle = stage.subtitle;
  if (idx === 5 && cu >= 18.2 && stage.lateSubtitle) {
    subtitle = stage.lateSubtitle;
  }

  return {
    stageIndex: idx,
    stage,
    opacity,
    subtitle
  };
}

const RADIUS_KNOTS = [
  [0, 9.5],
  [2, 13.5],
  [6, 24.5],
  [11, 41.5],
  [14, 56.5],
  [16, 72.5],
  [20, 96.0]
];

const _camPos = new THREE.Vector3();
const _camTarget = new THREE.Vector3();

export function getCameraState(u) {
  const cu = clamp(u, 0, DURATION);
  const R = sampleMonotonicSpline(RADIUS_KNOTS, cu);
  const theta = 0.18 * cu;
  const phi = 0.22 * Math.sin(cu * 0.23 + 0.4);

  const cosPhi = Math.cos(phi);
  _camPos.set(
    R * cosPhi * Math.sin(theta),
    R * Math.sin(phi),
    R * cosPhi * Math.cos(theta)
  );

  // Tangent forward along orbital motion (counter-clockwise around Y)
  const tanX = Math.cos(theta);
  const tanZ = -Math.sin(theta);

  // Stage 1: look dead center at the blinding Planck core (0,0,0)
  // Stages 2-5: gently offset target tangentially & slightly inward so active shell structures fill the view
  // Stage 6: drift gaze slightly more tangentially across the expansive cooling plasma fog
  const midStageBias = smoothstep(2.0, 5.5, cu) * (1.0 - smoothstep(14.5, 17.5, cu));
  const lateSweep = smoothstep(15.5, 19.2, cu);

  const radialAnchor = lerp(0.0, 0.28 * R, midStageBias) + lerp(0.0, 0.56 * R, lateSweep);
  const tangentShift = lerp(0.0, 4.2, midStageBias) + lerp(0.0, 18.0, lateSweep);
  const verticalShift = lerp(0.0, 1.4 * Math.sin(cu * 0.35), midStageBias + lateSweep);

  const dirToCamX = cosPhi * Math.sin(theta);
  const dirToCamY = Math.sin(phi);
  const dirToCamZ = cosPhi * Math.cos(theta);

  _camTarget.set(
    dirToCamX * radialAnchor + tanX * tangentShift,
    dirToCamY * radialAnchor + verticalShift,
    dirToCamZ * radialAnchor + tanZ * tangentShift
  );

  // Focus distance targets the active shell midplane right in front of the camera
  const focusDist = clamp(
    lerp(9.5, 18.0, smoothstep(0.0, 14.0, cu)) + lerp(0.0, 14.0, lateSweep),
    8.0,
    36.0
  );

  return {
    position: _camPos.clone(),
    target: _camTarget.clone(),
    fov: 68,
    focusDist
  };
}

// Linear HDR color keys per epoch (richly saturated below bloom threshold so hero VFX pop)
const PALETTE_KEYS = [
  {
    u: 0.0,
    bgPrimary: [0.14, 0.36, 0.92],
    bgSecondary: [0.05, 0.14, 0.56],
    fogColor: [0.11, 0.28, 0.80],
    coreColor: [1.55, 1.98, 2.85],
    bloomStrength: 0.52,
    shimmerStrength: 1.0
  },
  {
    u: 2.0,
    bgPrimary: [0.10, 0.30, 0.84],
    bgSecondary: [0.05, 0.14, 0.54],
    fogColor: [0.09, 0.24, 0.74],
    coreColor: [1.30, 1.72, 2.50],
    bloomStrength: 0.50,
    shimmerStrength: 0.82
  },
  {
    u: 4.5,
    bgPrimary: [0.07, 0.18, 0.58],
    bgSecondary: [0.10, 0.08, 0.40],
    fogColor: [0.08, 0.16, 0.52],
    coreColor: [0.95, 1.35, 2.15],
    bloomStrength: 0.48,
    shimmerStrength: 0.42
  },
  {
    u: 7.5,
    bgPrimary: [0.26, 0.05, 0.10],
    bgSecondary: [0.14, 0.03, 0.24],
    fogColor: [0.22, 0.04, 0.14],
    coreColor: [1.20, 0.65, 0.45],
    bloomStrength: 0.48,
    shimmerStrength: 0.28
  },
  {
    u: 11.5,
    bgPrimary: [0.32, 0.10, 0.035],
    bgSecondary: [0.18, 0.045, 0.025],
    fogColor: [0.28, 0.085, 0.03],
    coreColor: [1.35, 0.78, 0.35],
    bloomStrength: 0.46,
    shimmerStrength: 0.16
  },
  {
    u: 14.8,
    bgPrimary: [0.36, 0.13, 0.04],
    bgSecondary: [0.22, 0.06, 0.025],
    fogColor: [0.32, 0.11, 0.035],
    coreColor: [1.55, 0.98, 0.48],
    bloomStrength: 0.56,
    shimmerStrength: 0.08
  },
  {
    u: 17.5,
    bgPrimary: [0.34, 0.11, 0.03],
    bgSecondary: [0.20, 0.055, 0.018],
    fogColor: [0.30, 0.095, 0.028],
    coreColor: [1.05, 0.55, 0.22],
    bloomStrength: 0.38,
    shimmerStrength: 0.0
  },
  {
    u: 20.0,
    bgPrimary: [0.32, 0.10, 0.028],
    bgSecondary: [0.18, 0.048, 0.015],
    fogColor: [0.28, 0.085, 0.024],
    coreColor: [0.85, 0.42, 0.18],
    bloomStrength: 0.30,
    shimmerStrength: 0.0
  }
];

function lerpVec3(a, b, t, out) {
  return out.set(lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t));
}

const _bgPrimary = new THREE.Color();
const _bgSecondary = new THREE.Color();
const _fogColor = new THREE.Color();
const _coreColor = new THREE.Color();

export function getEpochPalette(u) {
  const cu = clamp(u, 0, DURATION);
  let k0 = PALETTE_KEYS[0];
  let k1 = PALETTE_KEYS[PALETTE_KEYS.length - 1];
  for (let i = 0; i < PALETTE_KEYS.length - 1; i++) {
    if (cu <= PALETTE_KEYS[i + 1].u || i === PALETTE_KEYS.length - 2) {
      k0 = PALETTE_KEYS[i];
      k1 = PALETTE_KEYS[i + 1];
      break;
    }
  }
  const rawT = clamp((cu - k0.u) / Math.max(1e-6, k1.u - k0.u), 0, 1);
  const t = rawT * rawT * (3 - 2 * rawT);

  const bgPrimary = lerpVec3(k0.bgPrimary, k1.bgPrimary, t, new THREE.Vector3());
  const bgSecondary = lerpVec3(k0.bgSecondary, k1.bgSecondary, t, new THREE.Vector3());
  const fogColor = lerpVec3(k0.fogColor, k1.fogColor, t, new THREE.Vector3());
  const coreColor = lerpVec3(k0.coreColor, k1.coreColor, t, new THREE.Vector3());

  _bgPrimary.setRGB(bgPrimary.x, bgPrimary.y, bgPrimary.z);
  _bgSecondary.setRGB(bgSecondary.x, bgSecondary.y, bgSecondary.z);
  _fogColor.setRGB(fogColor.x, fogColor.y, fogColor.z);
  _coreColor.setRGB(coreColor.x, coreColor.y, coreColor.z);

  return {
    bgPrimary: _bgPrimary.clone(),
    bgSecondary: _bgSecondary.clone(),
    fogColor: _fogColor.clone(),
    coreColor: _coreColor.clone(),
    bloomStrength: lerp(k0.bloomStrength, k1.bloomStrength, t),
    shimmerStrength: lerp(k0.shimmerStrength, k1.shimmerStrength, t)
  };
}
