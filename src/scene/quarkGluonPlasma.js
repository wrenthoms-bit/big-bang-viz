import * as THREE from 'three';

const QUARK_VERT = /* glsl */ `
attribute vec4 aSeed;
attribute float aShellRadius;
attribute float aColorClass;
attribute float aSize;
attribute float aSpeed;

uniform float uTime;
uniform float uWeight;
uniform float uFocusDist;
uniform vec3 uCamPos;

varying vec2 vUv;
varying vec3 vColor;
varying float vAlpha;

vec3 swirlPos(vec4 seed, float radius, float speed, float t) {
  float theta0 = seed.x * 6.283185;
  float phi0 = (seed.y - 0.5) * 2.55;
  float swirlRate = speed * (0.42 + 0.35 * seed.z);
  float theta = theta0 + t * swirlRate + 0.45 * sin(t * 0.9 + seed.w * 6.28318);
  float phi = phi0 + 0.35 * sin(t * 1.15 * speed + seed.x * 12.0);

  // Breathing radial turbulence
  float r = radius + 2.6 * sin(t * 1.3 + seed.w * 10.0) + 1.4 * cos(theta * 3.0 - t * 1.8);
  float cosP = cos(phi);
  vec3 base = vec3(r * cosP * cos(theta), r * sin(phi), r * cosP * sin(theta));

  // Analytical 3D curl-like turbulence offset
  vec3 turb = vec3(
    sin(base.y * 0.16 + t * 1.7 + seed.z * 5.0),
    cos(base.z * 0.15 - t * 1.5 + seed.x * 5.0),
    sin(base.x * 0.17 + t * 1.9 + seed.y * 5.0)
  ) * 2.4;

  return base + turb;
}

void main() {
  vUv = uv;

  vec3 p = swirlPos(aSeed, aShellRadius, aSpeed, uTime);
  vec3 pNext = swirlPos(aSeed, aShellRadius, aSpeed, uTime + 0.045);
  vec3 vel = pNext - p;
  float speedLen = max(length(vel), 0.001);
  vec3 dir = vel / speedLen;

  vec3 toCam = normalize(uCamPos - p);
  vec3 side = normalize(cross(dir, toCam));
  if (length(cross(dir, toCam)) < 0.001) {
    side = vec3(0.0, 1.0, 0.0);
  }

  vec4 mvCenter = modelViewMatrix * vec4(p, 1.0);
  float dof = clamp(abs(-mvCenter.z - uFocusDist) * 0.028, 0.0, 1.0);

  float streakLen = aSize * (2.0 + 7.2 * speedLen) * (1.0 + 0.45 * dof);
  float streakWidth = aSize * (0.68 + 0.55 * dof);

  vec3 worldPos = p + dir * (position.x * streakLen) + side * (position.y * streakWidth);
  gl_Position = projectionMatrix * modelViewMatrix * vec4(worldPos, 1.0);

  // Richly saturated orange, crimson-red, and electric violet quark-gluon color classes
  vec3 cOrange = vec3(1.95, 0.52, 0.04);
  vec3 cRed    = vec3(1.80, 0.07, 0.10);
  vec3 cViolet = vec3(0.95, 0.14, 1.95);

  vec3 col = aColorClass < 0.5 ? cOrange : (aColorClass < 1.5 ? cRed : cViolet);
  float shimmer = 0.72 + 0.28 * sin(uTime * 4.5 + aSeed.w * 25.0);
  vColor = col * (0.78 + 0.32 * shimmer);
  vAlpha = uWeight * 0.24 * (0.45 + 0.55 * shimmer) * (1.0 - 0.45 * dof);
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
  float along = d.x;
  float across = d.y;
  float dist2 = along * along * 0.85 + across * across * 1.45;
  if (dist2 > 1.0) discard;

  float core = exp(-dist2 * 4.2) * (1.0 - dist2);
  vec3 hot = mix(vColor, vec3(2.6, 2.2, 2.0), core * 0.35);
  gl_FragColor = vec4(hot * core * vAlpha, core * vAlpha);
}
`;

const FILAMENT_VERT = /* glsl */ `
attribute vec4 aSeed;
attribute float aRadius;
attribute float aColorClass;

uniform float uTime;
uniform float uWeight;
uniform vec3 uCamPos;

varying vec2 vUv;
varying vec3 vColor;
varying float vAlpha;

vec3 filamentPoint(float s, vec4 seed, float rad, float t) {
  float theta = seed.x * 6.283185 + s * (0.85 + 0.75 * seed.z) + t * (0.28 + 0.22 * seed.w);
  float phi = (seed.y - 0.5) * 2.3 + 0.42 * sin(s * 3.14159 * 1.5 + t * 1.2 + seed.w * 6.28);
  float r = rad + 3.2 * sin(s * 6.283 + t * 1.4 + seed.x * 8.0);
  float cosP = cos(phi);
  vec3 p = vec3(r * cosP * cos(theta), r * sin(phi), r * cosP * sin(theta));
  p += vec3(
    sin(p.y * 0.14 + t * 1.3),
    cos(p.z * 0.14 - t * 1.1),
    sin(p.x * 0.14 + t * 1.5)
  ) * 1.9;
  return p;
}

void main() {
  // position.x in [0, 1] along filament, position.y in [-0.5, 0.5] across ribbon
  vUv = vec2(position.x, position.y + 0.5);

  vec3 p = filamentPoint(position.x, aSeed, aRadius, uTime);
  vec3 pNext = filamentPoint(position.x + 0.025, aSeed, aRadius, uTime);
  vec3 tangent = normalize(pNext - p + vec3(1e-5));
  vec3 toCam = normalize(uCamPos - p);
  vec3 side = normalize(cross(tangent, toCam));
  if (length(cross(tangent, toCam)) < 0.001) {
    side = vec3(0.0, 1.0, 0.0);
  }

  float taper = sin(position.x * 3.14159265);
  float width = (0.14 + 0.16 * aSeed.w) * (0.35 + 0.65 * taper);
  vec3 worldPos = p + side * position.y * width;

  vec3 cOrange = vec3(1.95, 0.58, 0.06);
  vec3 cCrimson = vec3(1.80, 0.10, 0.14);
  vec3 cViolet = vec3(1.05, 0.18, 2.05);

  vColor = aColorClass < 0.5 ? cOrange : (aColorClass < 1.5 ? cCrimson : cViolet);
  vAlpha = uWeight * taper * 0.52 * (0.65 + 0.35 * sin(uTime * 2.5 + aSeed.y * 12.0));

  gl_Position = projectionMatrix * modelViewMatrix * vec4(worldPos, 1.0);
}
`;

const FILAMENT_FRAG = /* glsl */ `
precision highp float;

uniform float uTime;

varying vec2 vUv;
varying vec3 vColor;
varying float vAlpha;

void main() {
  if (vAlpha < 0.004) discard;
  float crossDist = abs(vUv.y - 0.5) * 2.0;
  float profile = exp(-crossDist * crossDist * 4.5);

  // Energy pulses racing along gluon filament
  float pulse = 0.5 + 0.5 * sin(vUv.x * 16.0 - uTime * 7.5);
  float knot = pow(pulse, 3.0);

  vec3 col = vColor * (0.85 + 1.15 * knot) + vec3(2.2, 1.8, 1.5) * knot * 0.4;
  gl_FragColor = vec4(col * profile * vAlpha, profile * vAlpha * 0.85);
}
`;

export function createQuarkGluonPlasma() {
  const group = new THREE.Group();

  let s = 4242;
  const rand = () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };

  // System A: 18,000 GPU-instanced quark/gluon swirling stream streaks
  const STREAM_COUNT = 18000;
  const baseQuad = new THREE.PlaneGeometry(1, 1);
  const streamGeo = new THREE.InstancedBufferGeometry();
  streamGeo.index = baseQuad.index;
  streamGeo.attributes.position = baseQuad.attributes.position;
  streamGeo.attributes.uv = baseQuad.attributes.uv;
  streamGeo.instanceCount = STREAM_COUNT;

  const qSeeds = new Float32Array(STREAM_COUNT * 4);
  const qRadii = new Float32Array(STREAM_COUNT);
  const qColors = new Float32Array(STREAM_COUNT);
  const qSizes = new Float32Array(STREAM_COUNT);
  const qSpeeds = new Float32Array(STREAM_COUNT);

  for (let i = 0; i < STREAM_COUNT; i++) {
    qSeeds[i * 4 + 0] = rand();
    qSeeds[i * 4 + 1] = rand();
    qSeeds[i * 4 + 2] = rand();
    qSeeds[i * 4 + 3] = rand();

    qRadii[i] = 16.0 + rand() * 28.0;
    const cPick = rand();
    qColors[i] = cPick < 0.38 ? 0.0 : cPick < 0.72 ? 1.0 : 2.0;
    qSizes[i] = 0.16 + Math.pow(rand(), 1.5) * 0.34;
    qSpeeds[i] = 0.55 + rand() * 0.95;
  }

  streamGeo.setAttribute('aSeed', new THREE.InstancedBufferAttribute(qSeeds, 4));
  streamGeo.setAttribute('aShellRadius', new THREE.InstancedBufferAttribute(qRadii, 1));
  streamGeo.setAttribute('aColorClass', new THREE.InstancedBufferAttribute(qColors, 1));
  streamGeo.setAttribute('aSize', new THREE.InstancedBufferAttribute(qSizes, 1));
  streamGeo.setAttribute('aSpeed', new THREE.InstancedBufferAttribute(qSpeeds, 1));

  const streamUniforms = {
    uTime: { value: 0 },
    uWeight: { value: 0 },
    uFocusDist: { value: 14 },
    uCamPos: { value: new THREE.Vector3() }
  };

  const streamMat = new THREE.ShaderMaterial({
    vertexShader: QUARK_VERT,
    fragmentShader: QUARK_FRAG,
    uniforms: streamUniforms,
    transparent: true,
    depthWrite: false,
    side: THREE.DoubleSide,
    blending: THREE.AdditiveBlending
  });

  const streamMesh = new THREE.Mesh(streamGeo, streamMat);
  streamMesh.frustumCulled = false;
  streamMesh.renderOrder = 5;
  group.add(streamMesh);

  // System B: 420 GPU-instanced gluon energy filaments (24-segment curved ribbons)
  const FILAMENT_COUNT = 420;
  const SEGMENTS = 24;
  const ribbonBase = new THREE.BufferGeometry();
  const rVerts = [];
  const rIndices = [];
  for (let i = 0; i <= SEGMENTS; i++) {
    const x = i / SEGMENTS;
    rVerts.push(x, -0.5, 0, x, 0.5, 0);
    if (i < SEGMENTS) {
      const a = i * 2;
      rIndices.push(a, a + 1, a + 2, a + 1, a + 3, a + 2);
    }
  }
  ribbonBase.setAttribute('position', new THREE.Float32BufferAttribute(rVerts, 3));
  ribbonBase.setIndex(rIndices);

  const filamentGeo = new THREE.InstancedBufferGeometry();
  filamentGeo.index = ribbonBase.index;
  filamentGeo.attributes.position = ribbonBase.attributes.position;
  filamentGeo.instanceCount = FILAMENT_COUNT;

  const fSeeds = new Float32Array(FILAMENT_COUNT * 4);
  const fRadii = new Float32Array(FILAMENT_COUNT);
  const fColors = new Float32Array(FILAMENT_COUNT);

  for (let i = 0; i < FILAMENT_COUNT; i++) {
    fSeeds[i * 4 + 0] = rand();
    fSeeds[i * 4 + 1] = rand();
    fSeeds[i * 4 + 2] = rand();
    fSeeds[i * 4 + 3] = rand();
    fRadii[i] = 18.0 + rand() * 25.0;
    const cPick = rand();
    fColors[i] = cPick < 0.34 ? 0.0 : cPick < 0.66 ? 1.0 : 2.0;
  }

  filamentGeo.setAttribute('aSeed', new THREE.InstancedBufferAttribute(fSeeds, 4));
  filamentGeo.setAttribute('aRadius', new THREE.InstancedBufferAttribute(fRadii, 1));
  filamentGeo.setAttribute('aColorClass', new THREE.InstancedBufferAttribute(fColors, 1));

  const filamentUniforms = {
    uTime: { value: 0 },
    uWeight: { value: 0 },
    uCamPos: { value: new THREE.Vector3() }
  };

  const filamentMat = new THREE.ShaderMaterial({
    vertexShader: FILAMENT_VERT,
    fragmentShader: FILAMENT_FRAG,
    uniforms: filamentUniforms,
    transparent: true,
    depthWrite: false,
    side: THREE.DoubleSide,
    blending: THREE.AdditiveBlending
  });

  const filamentMesh = new THREE.Mesh(filamentGeo, filamentMat);
  filamentMesh.frustumCulled = false;
  filamentMesh.renderOrder = 6;
  group.add(filamentMesh);

  function update(u, camera, weights, _palette, focusDist) {
    const w = weights.qgp;
    group.visible = w > 0.002;
    if (!group.visible) return;

    streamUniforms.uTime.value = u;
    streamUniforms.uWeight.value = w;
    streamUniforms.uFocusDist.value = focusDist;
    streamUniforms.uCamPos.value.copy(camera.position);

    filamentUniforms.uTime.value = u;
    filamentUniforms.uWeight.value = w;
    filamentUniforms.uCamPos.value.copy(camera.position);
  }

  function dispose() {
    baseQuad.dispose();
    streamGeo.dispose();
    streamMat.dispose();
    ribbonBase.dispose();
    filamentGeo.dispose();
    filamentMat.dispose();
  }

  return { group, update, dispose };
}
