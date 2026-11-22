import * as THREE from 'three';
import { getCameraState } from '../timeline.js';

const TRIPLET_MATH_GLSL = /* glsl */ `
void getTripletBasis(vec4 seed, out vec3 uAxis, out vec3 vAxis) {
  float a = seed.x * 6.283185;
  float b = (seed.y - 0.5) * 3.14159;
  vec3 n = normalize(vec3(cos(a) * cos(b), sin(b), sin(a) * cos(b)));
  vec3 ref = abs(n.y) < 0.9 ? vec3(0.0, 1.0, 0.0) : vec3(1.0, 0.0, 0.0);
  uAxis = normalize(cross(ref, n));
  vAxis = normalize(cross(n, uAxis));
}

void computeTriplet(
  vec3 baseCenter,
  vec4 seed,
  float snapTime,
  float scale,
  float uTime,
  out vec3 center,
  out vec3 q0,
  out vec3 q1,
  out vec3 q2,
  out float snapProgress,
  out float flash
) {
  center = baseCenter + vec3(
    sin(uTime * 0.45 + seed.x * 6.283),
    cos(uTime * 0.38 + seed.y * 6.283),
    sin(uTime * 0.42 + seed.z * 6.283)
  ) * 0.42;

  vec3 uAxis, vAxis;
  getTripletBasis(seed, uAxis, vAxis);

  float pre Approach = smoothstep(snapTime - 1.6, snapTime, uTime);
  float preRadius = mix(2.45, 1.85, preApproach);

  snapProgress = clamp((uTime - snapTime) / 0.48, 0.0, 1.0);
  float snapEase = snapProgress >= 0.999
    ? 1.0
    : clamp(1.0 - exp(-6.8 * snapProgress) * cos(10.5 * snapProgress), 0.0, 1.12);

  float orbitR = mix(preRadius, 0.42, snapEase) * scale;
  float spinRate = mix(1.45, 3.1, snapProgress) + seed.w * 0.9;
  float angleBase = uTime * spinRate + seed.x * 6.283185 + snapEase * 0.85;

  q0 = center + (cos(angleBase) * uAxis + sin(angleBase) * vAxis) * orbitR;
  q1 = center + (cos(angleBase + 2.094395) * uAxis + sin(angleBase + 2.094395) * vAxis) * orbitR;
  q2 = center + (cos(angleBase + 4.188790) * uAxis + sin(angleBase + 4.188790) * vAxis) * orbitR;

  flash = exp(-pow((snapProgress - 0.38) / 0.22, 2.0)) * step(0.001, snapProgress);
}
`;

// Fix accidental space in GLSL variable name before emitting!
const TRIPLET_GLSL_CLEAN = TRIPLET_MATH_GLSL.replace('pre Approach', 'preApproach');

const QUARK_VERT = /* glsl */ `
attribute vec3 aCenter;
attribute vec4 aSeed;
attribute float aSnapTime;
attribute float aScale;
attribute float aQuarkIndex;

uniform float uTime;
uniform float uWeight;
uniform float uFocusDist;

varying vec2 vUv;
varying vec3 vColor;
varying float vAlpha;

${TRIPLET_GLSL_CLEAN}

void main() {
  vUv = uv;
  vec3 center, q0, q1, q2;
  float snapP, flash;
  computeTriplet(aCenter, aSeed, aSnapTime, aScale, uTime, center, q0, q1, q2, snapP, flash);

  vec3 pos = aQuarkIndex < 0.5 ? q0 : (aQuarkIndex < 1.5 ? q1 : q2);
  vec4 mvPos = modelViewMatrix * vec4(pos, 1.0);

  float dof = clamp(abs(-mvPos.z - uFocusDist) * 0.032, 0.0, 1.0);
  float size = (0.34 + 0.14 * flash) * aScale * (1.0 + 0.48 * dof);
  mvPos.xy += position.xy * size;
  gl_Position = projectionMatrix * mvPos;

  // Harmonious luminous QCD-inspired warm colors for the 3 quarks in a proton/neutron
  vec3 c0 = vec3(2.35, 1.05, 0.24); // hot amber-orange
  vec3 c1 = vec3(2.45, 1.95, 0.95); // incandescent gold-white
  vec3 c2 = vec3(2.20, 0.56, 0.72); // luminous coral-rose

  vec3 baseCol = aQuarkIndex < 0.5 ? c0 : (aQuarkIndex < 1.5 ? c1 : c2);
  float heroBoost = mix(0.32, 1.0, smoothstep(1.08, 1.18, aScale));
  vColor = mix(baseCol, vec3(2.8, 2.4, 1.8), flash * 0.55);
  vAlpha = uWeight * heroBoost * (1.0 - 0.36 * dof);
}
`;

const QUARK_FRAG = /* glsl */ `
precision highp float;

varying vec2 vUv;
varying vec3 vColor;
varying float vAlpha;

void main() {
  if (vAlpha < 0.004) discard;
  vec2 d = vUv * 2.0 - 1.0;
  float r2 = dot(d, d);
  if (r2 > 1.0) discard;
  float core = exp(-r2 * 5.0);
  float halo = exp(-r2 * 1.9) * 0.42;
  float glow = (core + halo) * (1.0 - r2);
  gl_FragColor = vec4(vColor * glow, glow * vAlpha);
}
`;

const STRUT_VERT = /* glsl */ `
attribute vec3 aCenter;
attribute vec4 aSeed;
attribute float aSnapTime;
attribute float aScale;
attribute float aEdgeIndex;

uniform float uTime;
uniform float uWeight;
uniform vec3 uCamPos;

varying vec2 vUv;
varying vec3 vColor;
varying float vAlpha;

${TRIPLET_GLSL_CLEAN}

void main() {
  // position.x in [0, 1], position.y in [-0.5, 0.5]
  vUv = vec2(position.x, position.y + 0.5);

  vec3 center, q0, q1, q2;
  float snapP, flash;
  computeTriplet(aCenter, aSeed, aSnapTime, aScale, uTime, center, q0, q1, q2, snapP, flash);

  vec3 pA = aEdgeIndex < 0.5 ? q0 : (aEdgeIndex < 1.5 ? q1 : q2);
  vec3 pB = aEdgeIndex < 0.5 ? q1 : (aEdgeIndex < 1.5 ? q2 : q0);

  vec3 p = mix(pA, pB, position.x);
  vec3 tangent = normalize(pB - pA + vec3(1e-5));
  vec3 toCam = normalize(uCamPos - p);
  vec3 side = normalize(cross(tangent, toCam));
  if (length(cross(tangent, toCam)) < 0.001) {
    side = vec3(0.0, 1.0, 0.0);
  }

  float thickness = (0.085 + 0.14 * flash + 0.03 * snapP) * aScale;
  vec3 worldPos = p + side * position.y * thickness;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(worldPos, 1.0);

  vec3 gluonGold = vec3(2.0, 1.15, 0.35);
  vec3 snapWhite = vec3(2.9, 2.55, 1.85);
  float heroBoost = mix(0.28, 1.0, smoothstep(1.08, 1.18, aScale));
  vColor = mix(gluonGold, snapWhite, flash * 0.8 + snapP * 0.25);
  vAlpha = uWeight * heroBoost * (0.48 + 0.52 * max(snapP, flash));
}
`;

const STRUT_FRAG = /* glsl */ `
precision highp float;

varying vec2 vUv;
varying vec3 vColor;
varying float vAlpha;

void main() {
  if (vAlpha < 0.004) discard;
  float crossDist = abs(vUv.y - 0.5) * 2.0;
  float core = exp(-crossDist * crossDist * 4.5);
  float endTaper = smoothstep(0.0, 0.12, vUv.x) * (1.0 - smoothstep(0.88, 1.0, vUv.x));
  float g = core * (0.35 + 0.65 * endTaper);
  gl_FragColor = vec4(vColor * g * vAlpha, g * vAlpha);
}
`;

const HALO_VERT = /* glsl */ `
attribute vec3 aCenter;
attribute vec4 aSeed;
attribute float aSnapTime;
attribute float aScale;

uniform float uTime;
uniform float uWeight;

varying vec2 vUv;
varying vec3 vColor;
varying float vAlpha;

${TRIPLET_GLSL_CLEAN}

void main() {
  vUv = uv;
  vec3 center, q0, q1, q2;
  float snapP, flash;
  computeTriplet(aCenter, aSeed, aSnapTime, aScale, uTime, center, q0, q1, q2, snapP, flash);

  vec4 mvPos = modelViewMatrix * vec4(center, 1.0);
  float boundGlow = smoothstep(0.25, 1.0, snapP);
  float size = (0.95 * boundGlow + 1.45 * flash) * aScale;
  mvPos.xy += position.xy * size;
  gl_Position = projectionMatrix * mvPos;

  vec3 warmAura = vec3(1.5, 0.82, 0.24);
  vec3 flashWhite = vec3(2.6, 2.1, 1.4);
  float heroBoost = mix(0.18, 0.72, smoothstep(1.08, 1.18, aScale));
  vColor = mix(warmAura, flashWhite, flash);
  vAlpha = uWeight * heroBoost * (0.36 * boundGlow + 0.68 * flash);
}
`;

const HALO_FRAG = /* glsl */ `
precision highp float;

varying vec2 vUv;
varying vec3 vColor;
varying float vAlpha;

void main() {
  if (vAlpha < 0.004) discard;
  vec2 d = vUv * 2.0 - 1.0;
  float r2 = dot(d, d);
  if (r2 > 1.0) discard;
  float glow = exp(-r2 * 3.4) * (1.0 - r2);
  gl_FragColor = vec4(vColor * glow * vAlpha, glow * vAlpha);
}
`;

export function createHadronization() {
  const group = new THREE.Group();

  const TOTAL_TRIPLETS = 3600;
  const HERO_TRIPLETS = 72;

  let s = 7777;
  const rand = () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };

  // Pre-compute triplet centers, seeds, snap times, scales
  const tCenters = new Float32Array(TOTAL_TRIPLETS * 3);
  const tSeeds = new Float32Array(TOTAL_TRIPLETS * 4);
  const tSnapTimes = new Float32Array(TOTAL_TRIPLETS);
  const tScales = new Float32Array(TOTAL_TRIPLETS);

  const forwardVec = new THREE.Vector3();
  const rightVec = new THREE.Vector3();
  const upVec = new THREE.Vector3();
  const worldUp = new THREE.Vector3(0, 1, 0);

  for (let i = 0; i < TOTAL_TRIPLETS; i++) {
    let cx, cy, cz, scale, snapTime;

    if (i < HERO_TRIPLETS) {
      // Place hero triplets directly along Stage 4 camera corridor (u = 11.4 .. 13.7)
      const uSample = 11.35 + (i / HERO_TRIPLETS) * 2.35;
      const cam = getCameraState(uSample);
      forwardVec.subVectors(cam.target, cam.position).normalize();
      rightVec.crossVectors(forwardVec, worldUp).normalize();
      upVec.crossVectors(rightVec, forwardVec).normalize();

      const depth = 8.5 + rand() * 14.5;
      const spreadX = (rand() - 0.5) * depth * 1.15;
      const spreadY = (rand() - 0.5) * depth * 0.72;

      cx = cam.position.x + forwardVec.x * depth + rightVec.x * spreadX + upVec.x * spreadY;
      cy = cam.position.y + forwardVec.y * depth + rightVec.y * spreadX + upVec.y * spreadY;
      cz = cam.position.z + forwardVec.z * depth + rightVec.z * spreadX + upVec.z * spreadY;

      scale = 1.15 + rand() * 0.35;
      // Stagger snap times around camera arrival so viewer watches active snapping + bound clusters
      snapTime = 11.3 + ((i % 12) / 12) * 1.85 + (rand() - 0.5) * 0.15;
    } else {
      // Shell 4 distribution (r = 34 .. 62)
      const theta = rand() * Math.PI * 2;
      const cosPhi = rand() * 2 - 1;
      const sinPhi = Math.sqrt(Math.max(0, 1 - cosPhi * cosPhi));
      const r = 34.0 + rand() * 28.0;

      cx = r * sinPhi * Math.cos(theta);
      cy = r * cosPhi;
      cz = r * sinPhi * Math.sin(theta);

      scale = 0.78 + rand() * 0.38;
      snapTime = 11.15 + rand() * 2.15;
    }

    tCenters[i * 3 + 0] = cx;
    tCenters[i * 3 + 1] = cy;
    tCenters[i * 3 + 2] = cz;

    tSeeds[i * 4 + 0] = rand();
    tSeeds[i * 4 + 1] = rand();
    tSeeds[i * 4 + 2] = rand();
    tSeeds[i * 4 + 3] = rand();

    tSnapTimes[i] = snapTime;
    tScales[i] = scale;
  }

  // Expand triplet arrays to 3 quarks per triplet (10,800 instances)
  const QUARK_COUNT = TOTAL_TRIPLETS * 3;
  const qCenters = new Float32Array(QUARK_COUNT * 3);
  const qSeeds = new Float32Array(QUARK_COUNT * 4);
  const qSnapTimes = new Float32Array(QUARK_COUNT);
  const qScales = new Float32Array(QUARK_COUNT);
  const qIndices = new Float32Array(QUARK_COUNT);

  const eIndices = new Float32Array(QUARK_COUNT);

  for (let i = 0; i < TOTAL_TRIPLETS; i++) {
    for (let k = 0; k < 3; k++) {
      const idx = i * 3 + k;
      qCenters[idx * 3 + 0] = tCenters[i * 3 + 0];
      qCenters[idx * 3 + 1] = tCenters[i * 3 + 1];
      qCenters[idx * 3 + 2] = tCenters[i * 3 + 2];

      qSeeds[idx * 4 + 0] = tSeeds[i * 4 + 0];
      qSeeds[idx * 4 + 1] = tSeeds[i * 4 + 1];
      qSeeds[idx * 4 + 2] = tSeeds[i * 4 + 2];
      qSeeds[idx * 4 + 3] = tSeeds[i * 4 + 3];

      qSnapTimes[idx] = tSnapTimes[i];
      qScales[idx] = tScales[i];
      qIndices[idx] = k;
      eIndices[idx] = k;
    }
  }

  // 1. Quarks Mesh
  const baseQuad = new THREE.PlaneGeometry(1, 1);
  const quarkGeo = new THREE.InstancedBufferGeometry();
  quarkGeo.index = baseQuad.index;
  quarkGeo.attributes.position = baseQuad.attributes.position;
  quarkGeo.attributes.uv = baseQuad.attributes.uv;
  quarkGeo.instanceCount = QUARK_COUNT;

  const qCenterAttr = new THREE.InstancedBufferAttribute(qCenters, 3);
  const qSeedAttr = new THREE.InstancedBufferAttribute(qSeeds, 4);
  const qSnapAttr = new THREE.InstancedBufferAttribute(qSnapTimes, 1);
  const qScaleAttr = new THREE.InstancedBufferAttribute(qScales, 1);

  quarkGeo.setAttribute('aCenter', qCenterAttr);
  quarkGeo.setAttribute('aSeed', qSeedAttr);
  quarkGeo.setAttribute('aSnapTime', qSnapAttr);
  quarkGeo.setAttribute('aScale', qScaleAttr);
  quarkGeo.setAttribute('aQuarkIndex', new THREE.InstancedBufferAttribute(qIndices, 1));

  const quarkUniforms = {
    uTime: { value: 0 },
    uWeight: { value: 0 },
    uFocusDist: { value: 16 }
  };

  const quarkMat = new THREE.ShaderMaterial({
    vertexShader: QUARK_VERT,
    fragmentShader: QUARK_FRAG,
    uniforms: quarkUniforms,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending
  });

  const quarkMesh = new THREE.Mesh(quarkGeo, quarkMat);
  quarkMesh.frustumCulled = false;
  quarkMesh.renderOrder = 8;
  group.add(quarkMesh);

  // 2. Gluon Binding Flux Struts Mesh (shares triplet buffers)
  const strutStrip = new THREE.BufferGeometry();
  strutStrip.setAttribute(
    'position',
    new THREE.Float32BufferAttribute([0, -0.5, 0, 0, 0.5, 0, 1, -0.5, 0, 1, 0.5, 0], 3)
  );
  strutStrip.setIndex([0, 1, 2, 1, 3, 2]);

  const strutGeo = new THREE.InstancedBufferGeometry();
  strutGeo.index = strutStrip.index;
  strutGeo.attributes.position = strutStrip.attributes.position;
  strutGeo.instanceCount = QUARK_COUNT;
  strutGeo.setAttribute('aCenter', qCenterAttr);
  strutGeo.setAttribute('aSeed', qSeedAttr);
  strutGeo.setAttribute('aSnapTime', qSnapAttr);
  strutGeo.setAttribute('aScale', qScaleAttr);
  strutGeo.setAttribute('aEdgeIndex', new THREE.InstancedBufferAttribute(eIndices, 1));

  const strutUniforms = {
    uTime: { value: 0 },
    uWeight: { value: 0 },
    uCamPos: { value: new THREE.Vector3() }
  };

  const strutMat = new THREE.ShaderMaterial({
    vertexShader: STRUT_VERT,
    fragmentShader: STRUT_FRAG,
    uniforms: strutUniforms,
    transparent: true,
    depthWrite: false,
    side: THREE.DoubleSide,
    blending: THREE.AdditiveBlending
  });

  const strutMesh = new THREE.Mesh(strutGeo, strutMat);
  strutMesh.frustumCulled = false;
  strutMesh.renderOrder = 7;
  group.add(strutMesh);

  // 3. Confinement Halo Cores Mesh (3,600 instances)
  const haloGeo = new THREE.InstancedBufferGeometry();
  haloGeo.index = baseQuad.index;
  haloGeo.attributes.position = baseQuad.attributes.position;
  haloGeo.attributes.uv = baseQuad.attributes.uv;
  haloGeo.instanceCount = TOTAL_TRIPLETS;

  haloGeo.setAttribute('aCenter', new THREE.InstancedBufferAttribute(tCenters, 3));
  haloGeo.setAttribute('aSeed', new THREE.InstancedBufferAttribute(tSeeds, 4));
  haloGeo.setAttribute('aSnapTime', new THREE.InstancedBufferAttribute(tSnapTimes, 1));
  haloGeo.setAttribute('aScale', new THREE.InstancedBufferAttribute(tScales, 1));

  const haloUniforms = {
    uTime: { value: 0 },
    uWeight: { value: 0 }
  };

  const haloMat = new THREE.ShaderMaterial({
    vertexShader: HALO_VERT,
    fragmentShader: HALO_FRAG,
    uniforms: haloUniforms,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending
  });

  const haloMesh = new THREE.Mesh(haloGeo, haloMat);
  haloMesh.frustumCulled = false;
  haloMesh.renderOrder = 6;
  group.add(haloMesh);

  function update(u, camera, weights, _palette, focusDist) {
    const w = weights.hadrons;
    group.visible = w > 0.002;
    if (!group.visible) return;

    quarkUniforms.uTime.value = u;
    quarkUniforms.uWeight.value = w;
    quarkUniforms.uFocusDist.value = focusDist;

    strutUniforms.uTime.value = u;
    strutUniforms.uWeight.value = w;
    strutUniforms.uCamPos.value.copy(camera.position);

    haloUniforms.uTime.value = u;
    haloUniforms.uWeight.value = w;
  }

  function dispose() {
    baseQuad.dispose();
    quarkGeo.dispose();
    quarkMat.dispose();
    strutStrip.dispose();
    strutGeo.dispose();
    strutMat.dispose();
    haloGeo.dispose();
    haloMat.dispose();
  }

  return { group, update, dispose };
}
