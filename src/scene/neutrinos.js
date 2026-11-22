import * as THREE from 'three';
import { getCameraState } from '../timeline.js';

const NEUTRINO_VERT = /* glsl */ `
attribute vec3 aOrigin;
attribute vec3 aDir;
attribute vec4 aSeed;

uniform float uTime;
uniform float uWeight;
uniform vec3 uCamPos;

varying vec2 vUv;
varying float vAlpha;

void main() {
  // position.x in [-0.5, 0.5] along velocity, position.y in [-0.5, 0.5] across streak width
  vUv = vec2(position.x + 0.5, position.y + 0.5);

  // Fast, free-streaming ballistic motion outward after ~15.8s
  float flightTime = max(0.0, uTime - 15.65 + aSeed.x * 1.6);
  float speed = 18.0 + 16.0 * aSeed.y;
  // Loop cycle gracefully inside Shell 6 so trails stream continuously through u = 16..18.8s
  float cycle = mod(flightTime * speed, 36.0);
  vec3 pos = aOrigin + aDir * (cycle - 14.0);

  vec3 toCam = normalize(uCamPos - pos);
  vec3 side = normalize(cross(aDir, toCam));
  if (length(cross(aDir, toCam)) < 0.001) {
    side = vec3(0.0, 1.0, 0.0);
  }

  float streakLen = 7.5 + 5.5 * aSeed.z;
  float streakWidth = 0.16 + 0.13 * aSeed.w;

  vec3 worldPos = pos + aDir * (position.x * streakLen) + side * (position.y * streakWidth);
  gl_Position = projectionMatrix * modelViewMatrix * vec4(worldPos, 1.0);

  float cycleFade = smoothstep(0.0, 5.0, cycle) * (1.0 - smoothstep(26.0, 36.0, cycle));
  vAlpha = uWeight * cycleFade * (0.20 + 0.18 * aSeed.w);
}
`;

const NEUTRINO_FRAG = /* glsl */ `
precision highp float;

varying vec2 vUv;
varying float vAlpha;

void main() {
  if (vAlpha < 0.004) discard;
  // Crisp leading head at vUv.x = 1.0, ghost-like fading wake toward vUv.x = 0.0
  float head = smoothstep(0.0, 0.88, vUv.x) * (1.0 - smoothstep(0.88, 1.0, vUv.x));
  float tail = pow(clamp(vUv.x, 0.0, 1.0), 2.2);
  float across = abs(vUv.y - 0.5) * 2.0;
  float profile = exp(-across * across * 5.2);

  float intensity = (0.38 * tail + 0.85 * head) * profile;
  vec3 paleGhost = vec3(0.72, 0.94, 1.38);
  gl_FragColor = vec4(paleGhost * intensity * vAlpha, intensity * vAlpha);
}
`;

export function createNeutrinos() {
  const group = new THREE.Group();

  const COUNT = 1600;
  const HERO_COUNT = 240;
  const baseQuad = new THREE.PlaneGeometry(1, 1);
  const geo = new THREE.InstancedBufferGeometry();
  geo.index = baseQuad.index;
  geo.attributes.position = baseQuad.attributes.position;
  geo.attributes.uv = baseQuad.attributes.uv;
  geo.instanceCount = COUNT;

  const origins = new Float32Array(COUNT * 3);
  const dirs = new Float32Array(COUNT * 3);
  const seeds = new Float32Array(COUNT * 4);

  let s = 31415;
  const rand = () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };

  const forwardVec = new THREE.Vector3();
  const rightVec = new THREE.Vector3();
  const upVec = new THREE.Vector3();
  const worldUp = new THREE.Vector3(0, 1, 0);
  const dir = new THREE.Vector3();

  for (let i = 0; i < COUNT; i++) {
    let ox, oy, oz;

    if (i < HERO_COUNT) {
      // Sightline corridor across Stage 6a (u = 16.0..18.4)
      const uSample = 16.0 + (i / HERO_COUNT) * 2.4;
      const cam = getCameraState(uSample);
      forwardVec.subVectors(cam.target, cam.position).normalize();
      rightVec.crossVectors(forwardVec, worldUp).normalize();
      upVec.crossVectors(rightVec, forwardVec).normalize();

      const depth = 11.0 + rand() * 34.0;
      const sx = (rand() - 0.5) * depth * 1.45;
      const sy = (rand() - 0.5) * depth * 0.95;

      ox = cam.position.x + forwardVec.x * depth + rightVec.x * sx + upVec.x * sy;
      oy = cam.position.y + forwardVec.y * depth + rightVec.y * sx + upVec.y * sy;
      oz = cam.position.z + forwardVec.z * depth + rightVec.z * sx + upVec.z * sy;
    } else {
      const theta = rand() * Math.PI * 2;
      const cosPhi = rand() * 2 - 1;
      const sinPhi = Math.sqrt(Math.max(0, 1 - cosPhi * cosPhi));
      const r = 64.0 + rand() * 44.0;

      ox = r * sinPhi * Math.cos(theta);
      oy = r * cosPhi;
      oz = r * sinPhi * Math.sin(theta);
    }

    origins[i * 3 + 0] = ox;
    origins[i * 3 + 1] = oy;
    origins[i * 3 + 2] = oz;

    // Stream outward from the core with slight isotropic scatter
    dir.set(ox, oy, oz).normalize();
    dir.x += (rand() - 0.5) * 0.42;
    dir.y += (rand() - 0.5) * 0.42;
    dir.z += (rand() - 0.5) * 0.42;
    dir.normalize();

    dirs[i * 3 + 0] = dir.x;
    dirs[i * 3 + 1] = dir.y;
    dirs[i * 3 + 2] = dir.z;

    seeds[i * 4 + 0] = rand();
    seeds[i * 4 + 1] = rand();
    seeds[i * 4 + 2] = rand();
    seeds[i * 4 + 3] = rand();
  }

  geo.setAttribute('aOrigin', new THREE.InstancedBufferAttribute(origins, 3));
  geo.setAttribute('aDir', new THREE.InstancedBufferAttribute(dirs, 3));
  geo.setAttribute('aSeed', new THREE.InstancedBufferAttribute(seeds, 4));

  const uniforms = {
    uTime: { value: 0 },
    uWeight: { value: 0 },
    uCamPos: { value: new THREE.Vector3() }
  };

  const mat = new THREE.ShaderMaterial({
    vertexShader: NEUTRINO_VERT,
    fragmentShader: NEUTRINO_FRAG,
    uniforms,
    transparent: true,
    depthWrite: false,
    side: THREE.DoubleSide,
    blending: THREE.AdditiveBlending
  });

  const mesh = new THREE.Mesh(geo, mat);
  mesh.frustumCulled = false;
  mesh.renderOrder = 12;
  group.add(mesh);

  function update(u, camera, weights) {
    const w = weights.neutrinos;
    group.visible = w > 0.002;
    if (!group.visible) return;

    uniforms.uTime.value = u;
    uniforms.uWeight.value = w;
    uniforms.uCamPos.value.copy(camera.position);
  }

  function dispose() {
    baseQuad.dispose();
    geo.dispose();
    mat.dispose();
  }

  return { group, update, dispose };
}
