import * as THREE from 'three';
import { getCameraState } from '../timeline.js';

const PAIR_VERT = /* glsl */ `
attribute vec3 aCenter;
attribute vec4 aSeed;
attribute float aAnnihilateTime;
attribute float aSide;
attribute float aScale;

uniform float uTime;
uniform float uWeight;
uniform float uFocusDist;

varying vec2 vUv;
varying vec3 vColor;
varying float vAlpha;

void main() {
  vUv = uv;

  float tLeft = aAnnihilateTime - uTime;
  if (tLeft <= 0.0) {
    gl_Position = vec4(2.0, 2.0, 2.0, 1.0);
    vAlpha = 0.0;
    return;
  }

  // Spiral inward over the 0.85s preceding annihilation
  float approach = clamp(tLeft / 0.85, 0.0, 1.0);
  float radius = (0.04 + 1.45 * pow(approach, 0.72)) * aScale;
  float spin = (1.0 - approach) * 10.5 + uTime * (1.8 + aSeed.w) + aSeed.x * 6.28318;

  // Orthonormal orbital plane per pair
  float a = aSeed.x * 6.283185;
  float b = (aSeed.y - 0.5) * 3.14159;
  vec3 normal = normalize(vec3(cos(a) * cos(b), sin(b), sin(a) * cos(b)));
  vec3 ref = abs(normal.y) < 0.9 ? vec3(0.0, 1.0, 0.0) : vec3(1.0, 0.0, 0.0);
  vec3 uAxis = normalize(cross(ref, normal));
  vec3 vAxis = normalize(cross(normal, uAxis));

  vec3 pos = aCenter + aSide * (cos(spin) * uAxis + sin(spin) * vAxis) * radius;
  vec4 mvPos = modelViewMatrix * vec4(pos, 1.0);

  float dof = clamp(abs(-mvPos.z - uFocusDist) * 0.03, 0.0, 1.0);
  float size = (0.34 + 0.14 * (1.0 - approach)) * aScale * (1.0 + 0.45 * dof);
  mvPos.xy += position.xy * size;
  gl_Position = projectionMatrix * mvPos;

  // Matter = warm amber-gold; Antimatter = cool ice-cyan
  vec3 cMatter = vec3(2.35, 1.25, 0.28);
  vec3 cAnti   = vec3(0.45, 1.95, 2.65);
  vColor = aSide > 0.0 ? cMatter : cAnti;

  float preFade = smoothstep(0.0, 0.04, tLeft);
  vAlpha = uWeight * preFade * (1.0 - 0.35 * dof);
}
`;

const PAIR_FRAG = /* glsl */ `
precision highp float;

varying vec2 vUv;
varying vec3 vColor;
varying float vAlpha;

void main() {
  if (vAlpha < 0.004) discard;
  vec2 d = vUv * 2.0 - 1.0;
  float r2 = dot(d, d);
  if (r2 > 1.0) discard;
  float glow = exp(-r2 * 4.8) * (1.0 - r2);
  gl_FragColor = vec4(vColor * glow, glow * vAlpha);
}
`;

const FLASH_VERT = /* glsl */ `
attribute vec3 aCenter;
attribute vec4 aSeed;
attribute float aAnnihilateTime;
attribute float aScale;

uniform float uTime;
uniform float uWeight;

varying vec2 vUv;
varying float vAge;
varying float vAlpha;

void main() {
  vUv = uv;
  float age = (uTime - aAnnihilateTime) / 0.52;
  if (age <= 0.0 || age >= 1.0) {
    gl_Position = vec4(2.0, 2.0, 2.0, 1.0);
    vAlpha = 0.0;
    vAge = 0.0;
    return;
  }

  vAge = age;
  vec4 mvPos = modelViewMatrix * vec4(aCenter, 1.0);
  float expand = 0.45 + 3.4 * pow(age, 0.65);
  float size = expand * aScale;
  mvPos.xy += position.xy * size;
  gl_Position = projectionMatrix * mvPos;

  vAlpha = uWeight * pow(1.0 - age, 1.15);
}
`;

const FLASH_FRAG = /* glsl */ `
precision highp float;

varying vec2 vUv;
varying float vAge;
varying float vAlpha;

void main() {
  if (vAlpha < 0.004) discard;
  vec2 d = vUv * 2.0 - 1.0;
  float r = length(d);
  if (r > 1.0) discard;

  // Blinding core burst early in flash lifetime
  float coreBurst = exp(-r * r * 12.0) * exp(-vAge * 4.2) * 4.5;

  // 8-point diffraction starburst flare
  float rayX = exp(-abs(d.y) * 20.0) * exp(-abs(d.x) * 3.8);
  float rayY = exp(-abs(d.x) * 20.0) * exp(-abs(d.y) * 3.8);
  vec2 dRot = vec2(d.x + d.y, d.x - d.y) * 0.7071;
  float rayD1 = exp(-abs(dRot.y) * 26.0) * exp(-abs(dRot.x) * 5.2);
  float rayD2 = exp(-abs(dRot.x) * 26.0) * exp(-abs(dRot.y) * 5.2);
  float rays = (rayX + rayY + 0.55 * (rayD1 + rayD2)) * exp(-vAge * 4.6) * 2.8;

  // Soft expanding photon shockwave pulse
  float ringRadius = 0.14 + 0.78 * pow(vAge, 0.75);
  float ringDist = abs(r - ringRadius);
  float ring = exp(-ringDist * ringDist * 85.0) * pow(1.0 - vAge, 1.35) * 1.15;

  vec3 cCore = vec3(3.6, 3.2, 2.7);
  vec3 cRing = vec3(2.2, 1.25, 0.45);

  vec3 col = cCore * (coreBurst + rays) + cRing * ring;
  float alpha = clamp((coreBurst * 0.45 + rays * 0.55 + ring * 0.6), 0.0, 1.0) * vAlpha;
  gl_FragColor = vec4(col * vAlpha, alpha);
}
`;

const REMNANT_VERT = /* glsl */ `
attribute vec3 aOffset;
attribute vec4 aSeed;

uniform float uTime;
uniform float uWeight;
uniform float uFocusDist;

varying vec2 vUv;
varying float vAlpha;

void main() {
  vUv = uv;
  vec3 drift = vec3(
    sin(uTime * 0.35 + aSeed.x * 6.283),
    cos(uTime * 0.30 + aSeed.y * 6.283),
    sin(uTime * 0.40 + aSeed.z * 6.283)
  ) * 0.85;

  vec4 mvPos = modelViewMatrix * vec4(aOffset + drift, 1.0);
  float dof = clamp(abs(-mvPos.z - uFocusDist) * 0.025, 0.0, 1.0);
  float size = (0.48 + 0.25 * aSeed.w) * (1.0 + 0.4 * dof);
  mvPos.xy += position.xy * size;
  gl_Position = projectionMatrix * mvPos;

  vAlpha = uWeight * (0.72 + 0.28 * sin(uTime * 2.2 + aSeed.w * 15.0));
}
`;

const REMNANT_FRAG = /* glsl */ `
precision highp float;

varying vec2 vUv;
varying float vAlpha;

void main() {
  if (vAlpha < 0.004) discard;
  vec2 d = vUv * 2.0 - 1.0;
  float r2 = dot(d, d);
  if (r2 > 1.0) discard;
  float glow = (exp(-r2 * 6.0) + 0.35 * exp(-r2 * 1.8)) * (1.0 - r2);
  vec3 col = vec3(2.45, 1.48, 0.46);
  gl_FragColor = vec4(col * glow * vAlpha, glow * vAlpha);
}
`;

export function createAnnihilation() {
  const group = new THREE.Group();

  const PAIR_COUNT = 3600;
  const HERO_PAIRS = 88;
  const REMNANT_COUNT = 75;

  let s = 9091;
  const rand = () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };

  const pCenters = new Float32Array(PAIR_COUNT * 3);
  const pSeeds = new Float32Array(PAIR_COUNT * 4);
  const pAnnihTimes = new Float32Array(PAIR_COUNT);
  const pScales = new Float32Array(PAIR_COUNT);

  const forwardVec = new THREE.Vector3();
  const rightVec = new THREE.Vector3();
  const upVec = new THREE.Vector3();
  const worldUp = new THREE.Vector3(0, 1, 0);

  for (let i = 0; i < PAIR_COUNT; i++) {
    let cx, cy, cz, scale, annihTime;

    if (i < HERO_PAIRS) {
      // Hero pairs right inside Stage 5 camera view (u = 14.2 .. 15.7)
      const uSample = 14.15 + (i / HERO_PAIRS) * 1.6;
      const cam = getCameraState(uSample);
      forwardVec.subVectors(cam.target, cam.position).normalize();
      rightVec.crossVectors(forwardVec, worldUp).normalize();
      upVec.crossVectors(rightVec, forwardVec).normalize();

      const depth = 9.0 + rand() * 17.0;
      const spreadX = (rand() - 0.5) * depth * 1.25;
      const spreadY = (rand() - 0.5) * depth * 0.78;

      cx = cam.position.x + forwardVec.x * depth + rightVec.x * spreadX + upVec.x * spreadY;
      cy = cam.position.y + forwardVec.y * depth + rightVec.y * spreadX + upVec.y * spreadY;
      cz = cam.position.z + forwardVec.z * depth + rightVec.z * spreadX + upVec.z * spreadY;

      scale = 1.1 + rand() * 0.45;
      annihTime = 14.18 + ((i % 16) / 16) * 1.45 + (rand() - 0.5) * 0.1;
    } else {
      const theta = rand() * Math.PI * 2;
      const cosPhi = rand() * 2 - 1;
      const sinPhi = Math.sqrt(Math.max(0, 1 - cosPhi * cosPhi));
      const r = 46.0 + rand() * 32.0;

      cx = r * sinPhi * Math.cos(theta);
      cy = r * cosPhi;
      cz = r * sinPhi * Math.sin(theta);

      scale = 0.8 + rand() * 0.4;
      annihTime = 14.08 + rand() * 1.58;
    }

    pCenters[i * 3 + 0] = cx;
    pCenters[i * 3 + 1] = cy;
    pCenters[i * 3 + 2] = cz;

    pSeeds[i * 4 + 0] = rand();
    pSeeds[i * 4 + 1] = rand();
    pSeeds[i * 4 + 2] = rand();
    pSeeds[i * 4 + 3] = rand();

    pAnnihTimes[i] = annihTime;
    pScales[i] = scale;
  }

  // Expand to 7,200 matter/antimatter particles (2 per pair)
  const PARTICLE_COUNT = PAIR_COUNT * 2;
  const mCenters = new Float32Array(PARTICLE_COUNT * 3);
  const mSeeds = new Float32Array(PARTICLE_COUNT * 4);
  const mTimes = new Float32Array(PARTICLE_COUNT);
  const mSides = new Float32Array(PARTICLE_COUNT);
  const mScales = new Float32Array(PARTICLE_COUNT);

  for (let i = 0; i < PAIR_COUNT; i++) {
    for (let side = 0; side < 2; side++) {
      const idx = i * 2 + side;
      mCenters[idx * 3 + 0] = pCenters[i * 3 + 0];
      mCenters[idx * 3 + 1] = pCenters[i * 3 + 1];
      mCenters[idx * 3 + 2] = pCenters[i * 3 + 2];

      mSeeds[idx * 4 + 0] = pSeeds[i * 4 + 0];
      mSeeds[idx * 4 + 1] = pSeeds[i * 4 + 1];
      mSeeds[idx * 4 + 2] = pSeeds[i * 4 + 2];
      mSeeds[idx * 4 + 3] = pSeeds[i * 4 + 3];

      mTimes[idx] = pAnnihTimes[i];
      mSides[idx] = side === 0 ? 1.0 : -1.0;
      mScales[idx] = pScales[i];
    }
  }

  const baseQuad = new THREE.PlaneGeometry(1, 1);

  // 1. Matter + Antimatter Pairs
  const pairGeo = new THREE.InstancedBufferGeometry();
  pairGeo.index = baseQuad.index;
  pairGeo.attributes.position = baseQuad.attributes.position;
  pairGeo.attributes.uv = baseQuad.attributes.uv;
  pairGeo.instanceCount = PARTICLE_COUNT;

  pairGeo.setAttribute('aCenter', new THREE.InstancedBufferAttribute(mCenters, 3));
  pairGeo.setAttribute('aSeed', new THREE.InstancedBufferAttribute(mSeeds, 4));
  pairGeo.setAttribute('aAnnihilateTime', new THREE.InstancedBufferAttribute(mTimes, 1));
  pairGeo.setAttribute('aSide', new THREE.InstancedBufferAttribute(mSides, 1));
  pairGeo.setAttribute('aScale', new THREE.InstancedBufferAttribute(mScales, 1));

  const pairUniforms = {
    uTime: { value: 0 },
    uWeight: { value: 0 },
    uFocusDist: { value: 18 }
  };

  const pairMat = new THREE.ShaderMaterial({
    vertexShader: PAIR_VERT,
    fragmentShader: PAIR_FRAG,
    uniforms: pairUniforms,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending
  });

  const pairMesh = new THREE.Mesh(pairGeo, pairMat);
  pairMesh.frustumCulled = false;
  pairMesh.renderOrder = 9;
  group.add(pairMesh);

  // 2. Annihilation Flashes & Shockwaves (3,600 instances)
  const flashGeo = new THREE.InstancedBufferGeometry();
  flashGeo.index = baseQuad.index;
  flashGeo.attributes.position = baseQuad.attributes.position;
  flashGeo.attributes.uv = baseQuad.attributes.uv;
  flashGeo.instanceCount = PAIR_COUNT;

  flashGeo.setAttribute('aCenter', new THREE.InstancedBufferAttribute(pCenters, 3));
  flashGeo.setAttribute('aSeed', new THREE.InstancedBufferAttribute(pSeeds, 4));
  flashGeo.setAttribute('aAnnihilateTime', new THREE.InstancedBufferAttribute(pAnnihTimes, 1));
  flashGeo.setAttribute('aScale', new THREE.InstancedBufferAttribute(pScales, 1));

  const flashUniforms = {
    uTime: { value: 0 },
    uWeight: { value: 0 }
  };

  const flashMat = new THREE.ShaderMaterial({
    vertexShader: FLASH_VERT,
    fragmentShader: FLASH_FRAG,
    uniforms: flashUniforms,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending
  });

  const flashMesh = new THREE.Mesh(flashGeo, flashMat);
  flashMesh.frustumCulled = false;
  flashMesh.renderOrder = 10;
  group.add(flashMesh);

  // 3. Sparse Surviving Matter Remnant (~75 lone clusters across Shell 5)
  const remOffsets = new Float32Array(REMNANT_COUNT * 3);
  const remSeeds = new Float32Array(REMNANT_COUNT * 4);
  for (let i = 0; i < REMNANT_COUNT; i++) {
    if (i < 16) {
      const cam = getCameraState(15.65);
      forwardVec.subVectors(cam.target, cam.position).normalize();
      rightVec.crossVectors(forwardVec, worldUp).normalize();
      upVec.crossVectors(rightVec, forwardVec).normalize();
      const depth = 11.0 + rand() * 18.0;
      const sx = (rand() - 0.5) * depth * 1.1;
      const sy = (rand() - 0.5) * depth * 0.65;
      remOffsets[i * 3 + 0] = cam.position.x + forwardVec.x * depth + rightVec.x * sx + upVec.x * sy;
      remOffsets[i * 3 + 1] = cam.position.y + forwardVec.y * depth + rightVec.y * sx + upVec.y * sy;
      remOffsets[i * 3 + 2] = cam.position.z + forwardVec.z * depth + rightVec.z * sx + upVec.z * sy;
    } else {
      const theta = rand() * Math.PI * 2;
      const cosPhi = rand() * 2 - 1;
      const sinPhi = Math.sqrt(Math.max(0, 1 - cosPhi * cosPhi));
      const r = 48.0 + rand() * 28.0;
      remOffsets[i * 3 + 0] = r * sinPhi * Math.cos(theta);
      remOffsets[i * 3 + 1] = r * cosPhi;
      remOffsets[i * 3 + 2] = r * sinPhi * Math.sin(theta);
    }
    remSeeds[i * 4 + 0] = rand();
    remSeeds[i * 4 + 1] = rand();
    remSeeds[i * 4 + 2] = rand();
    remSeeds[i * 4 + 3] = rand();
  }

  const remGeo = new THREE.InstancedBufferGeometry();
  remGeo.index = baseQuad.index;
  remGeo.attributes.position = baseQuad.attributes.position;
  remGeo.attributes.uv = baseQuad.attributes.uv;
  remGeo.instanceCount = REMNANT_COUNT;
  remGeo.setAttribute('aOffset', new THREE.InstancedBufferAttribute(remOffsets, 3));
  remGeo.setAttribute('aSeed', new THREE.InstancedBufferAttribute(remSeeds, 4));

  const remUniforms = {
    uTime: { value: 0 },
    uWeight: { value: 0 },
    uFocusDist: { value: 20 }
  };

  const remMat = new THREE.ShaderMaterial({
    vertexShader: REMNANT_VERT,
    fragmentShader: REMNANT_FRAG,
    uniforms: remUniforms,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending
  });

  const remMesh = new THREE.Mesh(remGeo, remMat);
  remMesh.frustumCulled = false;
  remMesh.renderOrder = 11;
  group.add(remMesh);

  function update(u, _camera, weights, _palette, focusDist) {
    const w = weights.matter;
    group.visible = w > 0.002;
    if (!group.visible) return;

    pairUniforms.uTime.value = u;
    pairUniforms.uWeight.value = w;
    pairUniforms.uFocusDist.value = focusDist;

    flashUniforms.uTime.value = u;
    flashUniforms.uWeight.value = w;

    remUniforms.uTime.value = u;
    remUniforms.uWeight.value = w;
    remUniforms.uFocusDist.value = focusDist;
  }

  function dispose() {
    baseQuad.dispose();
    pairGeo.dispose();
    pairMat.dispose();
    flashGeo.dispose();
    flashMat.dispose();
    remGeo.dispose();
    remMat.dispose();
  }

  return { group, update, dispose };
}
