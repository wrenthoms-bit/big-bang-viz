import * as THREE from 'three';

const BEAM_VERT = /* glsl */ `
attribute vec3 aStart;
attribute vec3 aEnd;
attribute float aOctave;

uniform float uTime;
uniform float uWeight;
uniform vec3 uCamPos;

varying vec2 vUv;
varying float vRippleCrest;
varying float vAlpha;

// Quantum ripples oscillate rapidly at u=2..2.8s, then freeze into stretched spacetime
vec3 rippleDisplacement(vec3 p, float t, float scale) {
  float freeze = smoothstep(2.35, 4.45, t);
  // Integrated phase velocity slows exponentially to freeze the pattern
  float jitterTime = mix(t * 2.2, 2.35 * 2.2 + 0.35, freeze);
  vec3 k = p * 0.32;
  float w1 = sin(k.x * 1.4 + k.y * 0.9 + jitterTime);
  float w2 = cos(k.y * 1.3 - k.z * 1.1 - jitterTime * 0.85);
  float w3 = sin(k.z * 1.6 + k.x * 0.7 + jitterTime * 0.7);
  vec3 disp = vec3(w2 - w3, w3 - w1, w1 - w2);
  float amp = (0.34 + 0.25 * freeze) * (0.75 + 0.25 * scale);
  return disp * amp;
}

float rippleIntensity(vec3 p, float t) {
  float freeze = smoothstep(2.35, 4.45, t);
  float jitterTime = mix(t * 2.2, 2.35 * 2.2 + 0.35, freeze);
  vec3 k = p * 0.32;
  float v = sin(k.x * 1.4 + k.y * 0.9 + jitterTime)
          + cos(k.y * 1.3 - k.z * 1.1 - jitterTime * 0.85)
          + sin(k.z * 1.6 + k.x * 0.7 + jitterTime * 0.7);
  return clamp(0.5 + 0.28 * v, 0.0, 1.0);
}

void main() {
  // position.x in [0, 1] along beam, position.y in [-0.5, 0.5] across thickness
  vUv = vec2(position.x, position.y + 0.5);

  float expandRate = 0.38;
  float phase = fract(max(0.0, uTime - 1.2) * expandRate + aOctave / 3.0);
  // Exponential stretch across 2^0 .. 2^2.2
  float scale = exp2(phase * 2.2);

  // Smooth birth/fade envelope for seamless infinite exponential inflation
  float octFade = smoothstep(0.0, 0.18, phase) * (1.0 - smoothstep(0.70, 1.0, phase));

  vec3 p0 = aStart * scale;
  vec3 p1 = aEnd * scale;
  vec3 pBase = mix(p0, p1, position.x);

  vec3 p = pBase + rippleDisplacement(aStart * 1.15 + (aEnd - aStart) * 1.15 * position.x, uTime, scale);

  // Compute local beam tangent and expand into camera-facing ribbon
  vec3 tangent = normalize((p1 - p0) + vec3(1e-5));
  vec3 toCam = normalize(uCamPos - p);
  vec3 side = normalize(cross(tangent, toCam));
  if (length(cross(tangent, toCam)) < 0.001) {
    side = vec3(1.0, 0.0, 0.0);
  }

  float thickness = (0.068 + 0.045 * scale * 0.35);
  vec3 worldPos = p + side * position.y * thickness;

  float radialDist = length(p);
  float shellMask = smoothstep(3.5, 9.5, radialDist) * (1.0 - smoothstep(30.0, 44.0, radialDist));

  vRippleCrest = rippleIntensity(aStart * 1.15 + (aEnd - aStart) * 1.15 * position.x, uTime);
  vAlpha = uWeight * octFade * shellMask;

  gl_Position = projectionMatrix * modelViewMatrix * vec4(worldPos, 1.0);
}
`;

const BEAM_FRAG = /* glsl */ `
precision highp float;

varying vec2 vUv;
varying float vRippleCrest;
varying float vAlpha;

void main() {
  if (vAlpha < 0.004) discard;
  float crossDist = abs(vUv.y - 0.5) * 2.0;
  float core = exp(-crossDist * crossDist * 5.2);

  vec3 baseCyan = vec3(0.45, 1.15, 2.15);
  vec3 rippleViolet = vec3(1.10, 0.88, 2.35);
  vec3 hotWhite = vec3(2.2, 2.6, 3.3);

  vec3 col = mix(baseCyan, rippleViolet, vRippleCrest * 0.72);
  col = mix(col, hotWhite, pow(vRippleCrest, 2.0) * 0.55 + core * 0.25);

  gl_FragColor = vec4(col * core * vAlpha * 1.15, core * vAlpha);
}
`;

const NODE_VERT = /* glsl */ `
attribute vec3 aNodePos;
attribute float aOctave;

uniform float uTime;
uniform float uWeight;

varying vec2 vUv;
varying float vRippleCrest;
varying float vAlpha;

vec3 rippleDisplacement(vec3 p, float t, float scale) {
  float freeze = smoothstep(2.35, 4.45, t);
  float jitterTime = mix(t * 2.2, 2.35 * 2.2 + 0.35, freeze);
  vec3 k = p * 0.32;
  float w1 = sin(k.x * 1.4 + k.y * 0.9 + jitterTime);
  float w2 = cos(k.y * 1.3 - k.z * 1.1 - jitterTime * 0.85);
  float w3 = sin(k.z * 1.6 + k.x * 0.7 + jitterTime * 0.7);
  vec3 disp = vec3(w2 - w3, w3 - w1, w1 - w2);
  float amp = (0.34 + 0.25 * freeze) * (0.75 + 0.25 * scale);
  return disp * amp;
}

float rippleIntensity(vec3 p, float t) {
  float freeze = smoothstep(2.35, 4.45, t);
  float jitterTime = mix(t * 2.2, 2.35 * 2.2 + 0.35, freeze);
  vec3 k = p * 0.32;
  float v = sin(k.x * 1.4 + k.y * 0.9 + jitterTime)
          + cos(k.y * 1.3 - k.z * 1.1 - jitterTime * 0.85)
          + sin(k.z * 1.6 + k.x * 0.7 + jitterTime * 0.7);
  return clamp(0.5 + 0.28 * v, 0.0, 1.0);
}

void main() {
  vUv = uv;
  float expandRate = 0.38;
  float phase = fract(max(0.0, uTime - 1.2) * expandRate + aOctave / 3.0);
  float scale = exp2(phase * 2.2);
  float octFade = smoothstep(0.0, 0.18, phase) * (1.0 - smoothstep(0.70, 1.0, phase));

  vec3 p = aNodePos * scale + rippleDisplacement(aNodePos * 1.15, uTime, scale);
  float radialDist = length(p);
  float shellMask = smoothstep(3.5, 9.5, radialDist) * (1.0 - smoothstep(30.0, 44.0, radialDist));

  vRippleCrest = rippleIntensity(aNodePos * 1.15, uTime);
  vAlpha = uWeight * octFade * shellMask;

  vec4 mvPos = modelViewMatrix * vec4(p, 1.0);
  float size = (0.35 + 0.38 * vRippleCrest) * (0.7 + 0.3 * scale);
  mvPos.xy += position.xy * size;
  gl_Position = projectionMatrix * mvPos;
}
`;

const NODE_FRAG = /* glsl */ `
precision highp float;

varying vec2 vUv;
varying float vRippleCrest;
varying float vAlpha;

void main() {
  if (vAlpha < 0.004) discard;
  vec2 d = vUv * 2.0 - 1.0;
  float r2 = dot(d, d);
  if (r2 > 1.0) discard;
  float glow = exp(-r2 * 4.5);
  vec3 c = mix(vec3(0.65, 1.5, 2.6), vec3(2.4, 2.2, 3.4), vRippleCrest);
  gl_FragColor = vec4(c * glow * vAlpha, glow * vAlpha);
}
`;

export function createInflationLattice() {
  const group = new THREE.Group();

  // Subdivided beam strip (8 segments along X from 0..1, width Y from -0.5..0.5)
  const SEGMENTS = 8;
  const stripGeo = new THREE.BufferGeometry();
  const verts = [];
  const indices = [];
  for (let i = 0; i <= SEGMENTS; i++) {
    const x = i / SEGMENTS;
    verts.push(x, -0.5, 0, x, 0.5, 0);
    if (i < SEGMENTS) {
      const a = i * 2;
      indices.push(a, a + 1, a + 2, a + 1, a + 3, a + 2);
    }
  }
  stripGeo.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
  stripGeo.setIndex(indices);

  // Build 3D cubic lattice coordinates across 3 nested octaves
  const N = 6; // 6x6x6 vertices -> coordinates from -10.5 to +10.5
  const spacing = 4.2;
  const half = ((N - 1) * spacing) * 0.5;

  const starts = [];
  const ends = [];
  const octaves = [];
  const nodePositions = [];
  const nodeOctaves = [];

  for (let oct = 0; oct < 3; oct++) {
    for (let ix = 0; ix < N; ix++) {
      for (let iy = 0; iy < N; iy++) {
        for (let iz = 0; iz < N; iz++) {
          const x = ix * spacing - half;
          const y = iy * spacing - half;
          const z = iz * spacing - half;

          nodePositions.push(x, y, z);
          nodeOctaves.push(oct);

          if (ix < N - 1) {
            starts.push(x, y, z);
            ends.push(x + spacing, y, z);
            octaves.push(oct);
          }
          if (iy < N - 1) {
            starts.push(x, y, z);
            ends.push(x, y + spacing, z);
            octaves.push(oct);
          }
          if (iz < N - 1) {
            starts.push(x, y, z);
            ends.push(x, y, z + spacing);
            octaves.push(oct);
          }
        }
      }
    }
  }

  const beamCount = octaves.length;
  const beamGeo = new THREE.InstancedBufferGeometry();
  beamGeo.index = stripGeo.index;
  beamGeo.attributes.position = stripGeo.attributes.position;
  beamGeo.instanceCount = beamCount;

  beamGeo.setAttribute('aStart', new THREE.InstancedBufferAttribute(new Float32Array(starts), 3));
  beamGeo.setAttribute('aEnd', new THREE.InstancedBufferAttribute(new Float32Array(ends), 3));
  beamGeo.setAttribute('aOctave', new THREE.InstancedBufferAttribute(new Float32Array(octaves), 1));

  const beamUniforms = {
    uTime: { value: 0 },
    uWeight: { value: 0 },
    uCamPos: { value: new THREE.Vector3() }
  };

  const beamMat = new THREE.ShaderMaterial({
    vertexShader: BEAM_VERT,
    fragmentShader: BEAM_FRAG,
    uniforms: beamUniforms,
    transparent: true,
    depthWrite: false,
    side: THREE.DoubleSide,
    blending: THREE.AdditiveBlending
  });

  const beamMesh = new THREE.Mesh(beamGeo, beamMat);
  beamMesh.frustumCulled = false;
  beamMesh.renderOrder = 3;
  group.add(beamMesh);

  // Vertex intersection nodes
  const baseQuad = new THREE.PlaneGeometry(1, 1);
  const nodeGeo = new THREE.InstancedBufferGeometry();
  nodeGeo.index = baseQuad.index;
  nodeGeo.attributes.position = baseQuad.attributes.position;
  nodeGeo.attributes.uv = baseQuad.attributes.uv;
  nodeGeo.instanceCount = nodeOctaves.length;

  nodeGeo.setAttribute('aNodePos', new THREE.InstancedBufferAttribute(new Float32Array(nodePositions), 3));
  nodeGeo.setAttribute('aOctave', new THREE.InstancedBufferAttribute(new Float32Array(nodeOctaves), 1));

  const nodeUniforms = {
    uTime: { value: 0 },
    uWeight: { value: 0 }
  };

  const nodeMat = new THREE.ShaderMaterial({
    vertexShader: NODE_VERT,
    fragmentShader: NODE_FRAG,
    uniforms: nodeUniforms,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending
  });

  const nodeMesh = new THREE.Mesh(nodeGeo, nodeMat);
  nodeMesh.frustumCulled = false;
  nodeMesh.renderOrder = 4;
  group.add(nodeMesh);

  function update(u, camera, weights) {
    const w = weights.inflation;
    group.visible = w > 0.002;
    if (!group.visible) return;

    beamUniforms.uTime.value = u;
    beamUniforms.uWeight.value = w;
    beamUniforms.uCamPos.value.copy(camera.position);

    nodeUniforms.uTime.value = u;
    nodeUniforms.uWeight.value = w;
  }

  function dispose() {
    stripGeo.dispose();
    beamGeo.dispose();
    beamMat.dispose();
    baseQuad.dispose();
    nodeGeo.dispose();
    nodeMat.dispose();
  }

  return { group, update, dispose };
}
