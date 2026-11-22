import * as THREE from 'three';

const BACKDROP_VERT = /* glsl */ `
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = vec4(position.xy, 0.0, 1.0);
}
`;

const BACKDROP_FRAG = /* glsl */ `
precision highp float;

varying vec2 vUv;

uniform vec3 uCamPos;
uniform vec3 uCamRight;
uniform vec3 uCamUp;
uniform vec3 uCamForward;
uniform float uTanHalfFov;
uniform float uAspect;
uniform float uTime;

uniform float uWPlanck;
uniform float uWInflation;
uniform float uWQgp;
uniform float uWHadrons;
uniform float uWMatter;
uniform float uWNeutrinos;
uniform float uWRipples;

uniform vec3 uBgPrimary;
uniform vec3 uBgSecondary;
uniform vec3 uFogColor;
uniform vec3 uCoreColor;

// Fast interleaved gradient noise for jittering ray steps without banding
float ign(vec2 fragCoord) {
  vec3 magic = vec3(0.06711056, 0.00583715, 52.9829189);
  return fract(magic.z * fract(dot(fragCoord, magic.xy)));
}

// Fast 3D trigonometric gyroid fBM (3 octaves, zero hash lookups)
float gyroid(vec3 p) {
  return dot(sin(p), cos(p.yzx));
}

float plasmaFbm(vec3 p, float t) {
  float v = 0.0;
  float a = 0.52;
  vec3 shift = vec3(t * 0.22, -t * 0.17, t * 0.19);
  for (int i = 0; i < 3; i++) {
    v += a * (0.5 + 0.33 * gyroid(p + shift));
    p = p * 2.07 + vec3(1.7, -2.3, 1.3);
    shift *= 1.45;
    a *= 0.48;
  }
  return clamp(v, 0.0, 1.5);
}

// Broad, gentle acoustic density ripples for cooling late plasma (Stage 6)
float acousticRipples(vec3 p, float t) {
  vec3 q = p * 0.145;
  float w1 = sin(q.x * 1.15 + q.y * 0.75 - t * 0.09) * cos(q.z * 1.05 + q.x * 0.45 + t * 0.07);
  float w2 = sin(q.y * 1.65 - q.z * 1.20 + t * 0.06) * cos(q.x * 1.35 - q.y * 0.55);
  float w3 = cos((q.x + q.y - q.z) * 0.85 + t * 0.05);
  return 0.48 * w1 + 0.32 * w2 + 0.20 * w3;
}

vec3 shellEpochTint(float r) {
  vec3 cPlanck = vec3(1.35, 1.75, 2.50);
  vec3 cInflat = vec3(0.14, 0.34, 0.88);
  vec3 cQgp    = vec3(0.55, 0.12, 0.24);
  vec3 cHadron = vec3(0.58, 0.22, 0.06);
  vec3 cMatter = vec3(0.68, 0.30, 0.08);
  vec3 cLate   = vec3(0.42, 0.13, 0.035);

  vec3 col = cPlanck;
  col = mix(col, cInflat, smoothstep(6.0, 14.0, r));
  col = mix(col, cQgp,    smoothstep(20.0, 32.0, r));
  col = mix(col, cHadron, smoothstep(38.0, 50.0, r));
  col = mix(col, cMatter, smoothstep(52.0, 66.0, r));
  col = mix(col, cLate,   smoothstep(68.0, 88.0, r));
  return col;
}

void main() {
  vec2 ndc = vUv * 2.0 - 1.0;
  vec3 rd = normalize(
    uCamForward +
    ndc.x * uAspect * uTanHalfFov * uCamRight +
    ndc.y * uTanHalfFov * uCamUp
  );
  vec3 ro = uCamPos;

  // Closest approach to origin (Planck core at 0,0,0)
  float b = dot(-ro, rd);
  vec3 closestPt = ro + rd * max(b, 0.0);
  float distToOrigin = length(closestPt);

  // Subtle jittered 18-step raymarch covering foreground -> deep opaque plasma
  float jitter = ign(gl_FragCoord.xy);
  const int STEPS = 18;
  float maxDist = mix(36.0, 128.0, smoothstep(0.0, 16.0, uTime));
  float stepLen = maxDist / float(STEPS);

  vec3 accum = vec3(0.0);
  float transmittance = 1.0;

  // Turbulence intensity relaxes gracefully in Stage 6 toward uniform glowing plasma
  float turbCalm = 1.0 - 0.84 * uWRipples;
  float noiseScale = mix(0.24, 0.075, smoothstep(0.0, 18.0, uTime));

  for (int i = 0; i < STEPS; i++) {
    float fi = float(i) + jitter;
    // Quadratic bias puts finer sampling closer to the camera & core
    float tNorm = fi / float(STEPS);
    float dist = maxDist * (0.04 + 0.96 * tNorm * tNorm);
    float dt = stepLen * (0.3 + 1.45 * tNorm);

    vec3 p = ro + rd * dist;
    float r = length(p);

    // 3D volumetric turbulence
    float turb = plasmaFbm(p * noiseScale, uTime * (0.85 - 0.55 * uWRipples));
    float rippleVal = acousticRipples(p, uTime);

    // Local opacity and emission
    float shellDensity = mix(0.036, 0.022, uWRipples);
    float density = shellDensity * (0.65 + 0.70 * turb * turbCalm + 0.22 * rippleVal * uWRipples);

    // Concentric radial shell color blended with current global epoch palette
    vec3 shellCol = shellEpochTint(r);
    vec3 envCol = mix(uBgSecondary, uBgPrimary, clamp(turb * 0.85, 0.0, 1.0));
    vec3 sampleCol = mix(envCol, shellCol, 0.42 * (1.0 - 0.72 * uWRipples));

    // Late Stage 6: smooth warm glowing plasma with subtle gold-amber vs ember-terracotta density ripples
    vec3 rippleCrest = vec3(0.66, 0.26, 0.065);
    vec3 rippleTrough = vec3(0.22, 0.062, 0.020);
    vec3 latePlasma = mix(rippleTrough, rippleCrest, clamp(0.5 + 0.58 * rippleVal, 0.0, 1.0));
    sampleCol = mix(sampleCol, latePlasma, uWRipples * 0.88);

    // Planck Core volumetric incandescence tightly focused at r < 5.5
    float coreFalloff = exp(-r * r / 9.5);
    float coronaFalloff = exp(-r / 6.2);
    float boil = plasmaFbm(p * 0.55 + vec3(0.0, uTime * 0.65, 0.0), uTime * 1.6);
    float coreEnergy = coreFalloff * (0.95 + 0.85 * boil) + 0.18 * coronaFalloff * (0.4 + boil);

    // Planck core stays blazing early and naturally shrinks into distance later
    float planckBoost = mix(0.65, 1.25, uWPlanck);
    sampleCol += uCoreColor * coreEnergy * planckBoost * 0.45;

    float stepAlpha = 1.0 - exp(-density * dt);
    accum += transmittance * sampleCol * stepAlpha * 1.04;
    transmittance *= (1.0 - stepAlpha);

    if (transmittance < 0.03) break;
  }

  // Direct blinding Planck Core radiance tight around (0,0,0)
  float coreRayBoost = exp(-(distToOrigin * distToOrigin) / mix(7.5, 11.0, uWPlanck));
  float camDist = length(ro);
  float distAtten = 1.0 / (1.0 + 0.0022 * camDist * camDist);
  float coreAngle = step(0.0, b);
  vec3 directCore = uCoreColor * coreRayBoost * coreAngle * distAtten * mix(0.25, 0.95, uWPlanck);

  // Guaranteed opaque background floor so NO pixel is ever dark/black
  float bgRipple = acousticRipples(ro + rd * 28.0, uTime);
  vec3 opaqueFloor = mix(uFogColor * 0.78, uBgPrimary * 0.92, 0.45 + 0.30 * bgRipple);
  vec3 lateFloor = mix(vec3(0.21, 0.06, 0.018), vec3(0.64, 0.25, 0.06), clamp(0.5 + 0.62 * bgRipple, 0.0, 1.0));
  opaqueFloor = mix(opaqueFloor, lateFloor, uWRipples * 0.88);

  vec3 finalColor = accum + transmittance * opaqueFloor + directCore;

  // Subtle coherent soft acoustic wave across the cooling plasma volume
  float viewRipple = acousticRipples(ro + rd * 24.0, uTime);
  vec3 rippleTint = mix(vec3(0.20, 0.055, 0.016), vec3(0.76, 0.31, 0.078), clamp(0.5 + 0.72 * viewRipple, 0.0, 1.0));
  finalColor = mix(finalColor, mix(finalColor, rippleTint, 0.65), uWRipples);

  // Subtle wide-angle radial energy vignette (never black, just warm/cool depth framing)
  float vig = 1.0 - 0.14 * dot(ndc, ndc);
  finalColor *= max(vig, 0.78);

  gl_FragColor = vec4(finalColor, 1.0);
}
`;

const FOAM_VERT = /* glsl */ `
attribute vec3 aOffset;
attribute vec4 aSeed;

uniform float uTime;
uniform float uOpacity;
uniform float uFocusDist;

varying vec2 vUv;
varying float vAlpha;
varying vec3 vColor;

void main() {
  vUv = uv;

  // Rapid sub-Planckian quantum fluctuation flickering
  float pulse = 0.5 + 0.5 * sin(uTime * (6.5 + aSeed.x * 9.0) + aSeed.y * 6.28318);
  float flicker = pow(pulse, 2.2);

  vec3 jitter = vec3(
    sin(uTime * 5.2 + aSeed.z * 20.0),
    cos(uTime * 4.7 + aSeed.w * 20.0),
    sin(uTime * 6.1 + aSeed.x * 20.0)
  ) * 0.42;

  vec3 worldPos = aOffset + jitter;
  vec4 mvPos = modelViewMatrix * vec4(worldPos, 1.0);

  float dof = clamp(abs(-mvPos.z - uFocusDist) * 0.04, 0.0, 1.0);
  float size = (0.14 + 0.24 * aSeed.w) * (0.65 + 0.85 * flicker) * (1.0 + 0.6 * dof);

  // Camera-facing billboard offset
  mvPos.xy += position.xy * size;
  gl_Position = projectionMatrix * mvPos;

  vAlpha = uOpacity * (0.28 + 0.72 * flicker) * (1.0 - 0.35 * dof);
  vec3 blueWhite = vec3(1.5, 2.1, 3.2);
  vec3 pureWhite = vec3(2.8, 3.0, 3.5);
  vColor = mix(blueWhite, pureWhite, aSeed.z * flicker);
}
`;

const FOAM_FRAG = /* glsl */ `
precision highp float;

varying vec2 vUv;
varying float vAlpha;
varying vec3 vColor;

void main() {
  vec2 d = vUv * 2.0 - 1.0;
  float r2 = dot(d, d);
  if (r2 > 1.0) discard;
  float glow = exp(-r2 * 4.2) * (1.0 - r2);
  gl_FragColor = vec4(vColor * glow, glow * vAlpha);
}
`;

export function createPlasmaBackdrop() {
  const group = new THREE.Group();

  // 1. Volumetric Raymarched Opaque Plasma Backdrop
  const quadGeo = new THREE.PlaneGeometry(2, 2);
  const backdropUniforms = {
    uCamPos: { value: new THREE.Vector3() },
    uCamRight: { value: new THREE.Vector3(1, 0, 0) },
    uCamUp: { value: new THREE.Vector3(0, 1, 0) },
    uCamForward: { value: new THREE.Vector3(0, 0, -1) },
    uTanHalfFov: { value: Math.tan(THREE.MathUtils.degToRad(68 * 0.5)) },
    uAspect: { value: 16 / 9 },
    uTime: { value: 0 },
    uWPlanck: { value: 1 },
    uWInflation: { value: 0 },
    uWQgp: { value: 0 },
    uWHadrons: { value: 0 },
    uWMatter: { value: 0 },
    uWNeutrinos: { value: 0 },
    uWRipples: { value: 0 },
    uBgPrimary: { value: new THREE.Color(0.65, 0.86, 1.35) },
    uBgSecondary: { value: new THREE.Color(0.35, 0.58, 1.15) },
    uFogColor: { value: new THREE.Color(0.58, 0.82, 1.30) },
    uCoreColor: { value: new THREE.Color(2.6, 3.1, 4.2) }
  };

  const backdropMat = new THREE.ShaderMaterial({
    vertexShader: BACKDROP_VERT,
    fragmentShader: BACKDROP_FRAG,
    uniforms: backdropUniforms,
    depthTest: false,
    depthWrite: false
  });

  const backdropMesh = new THREE.Mesh(quadGeo, backdropMat);
  backdropMesh.frustumCulled = false;
  backdropMesh.renderOrder = -100;
  group.add(backdropMesh);

  // 2. Planck Quantum Foam Sparks (2,500 GPU-instanced billboards near r = 2..11.5)
  const FOAM_COUNT = 2500;
  const baseQuad = new THREE.PlaneGeometry(1, 1);
  const foamGeo = new THREE.InstancedBufferGeometry();
  foamGeo.index = baseQuad.index;
  foamGeo.attributes.position = baseQuad.attributes.position;
  foamGeo.attributes.uv = baseQuad.attributes.uv;
  foamGeo.instanceCount = FOAM_COUNT;

  const offsets = new Float32Array(FOAM_COUNT * 3);
  const seeds = new Float32Array(FOAM_COUNT * 4);

  // Deterministic pseudo-random generator
  let s = 1337;
  const rand = () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };

  for (let i = 0; i < FOAM_COUNT; i++) {
    const theta = rand() * Math.PI * 2;
    const cosPhi = rand() * 2 - 1;
    const sinPhi = Math.sqrt(Math.max(0, 1 - cosPhi * cosPhi));
    const r = 2.0 + Math.pow(rand(), 0.72) * 9.5;

    offsets[i * 3 + 0] = r * sinPhi * Math.cos(theta);
    offsets[i * 3 + 1] = r * cosPhi;
    offsets[i * 3 + 2] = r * sinPhi * Math.sin(theta);

    seeds[i * 4 + 0] = rand();
    seeds[i * 4 + 1] = rand();
    seeds[i * 4 + 2] = rand();
    seeds[i * 4 + 3] = rand();
  }

  foamGeo.setAttribute('aOffset', new THREE.InstancedBufferAttribute(offsets, 3));
  foamGeo.setAttribute('aSeed', new THREE.InstancedBufferAttribute(seeds, 4));

  const foamUniforms = {
    uTime: { value: 0 },
    uOpacity: { value: 1 },
    uFocusDist: { value: 9.5 }
  };

  const foamMat = new THREE.ShaderMaterial({
    vertexShader: FOAM_VERT,
    fragmentShader: FOAM_FRAG,
    uniforms: foamUniforms,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending
  });

  const foamMesh = new THREE.Mesh(foamGeo, foamMat);
  foamMesh.frustumCulled = false;
  foamMesh.renderOrder = 2;
  group.add(foamMesh);

  const _right = new THREE.Vector3();
  const _up = new THREE.Vector3();
  const _forward = new THREE.Vector3();

  function update(u, camera, weights, palette, focusDist) {
    camera.matrixWorld.extractBasis(_right, _up, _forward);
    _forward.negate(); // camera looks down -Z in local space

    backdropUniforms.uCamPos.value.copy(camera.position);
    backdropUniforms.uCamRight.value.copy(_right);
    backdropUniforms.uCamUp.value.copy(_up);
    backdropUniforms.uCamForward.value.copy(_forward);
    backdropUniforms.uTanHalfFov.value = Math.tan(THREE.MathUtils.degToRad(camera.fov * 0.5));
    backdropUniforms.uAspect.value = camera.aspect;
    backdropUniforms.uTime.value = u;

    backdropUniforms.uWPlanck.value = weights.planck;
    backdropUniforms.uWInflation.value = weights.inflation;
    backdropUniforms.uWQgp.value = weights.qgp;
    backdropUniforms.uWHadrons.value = weights.hadrons;
    backdropUniforms.uWMatter.value = weights.matter;
    backdropUniforms.uWNeutrinos.value = weights.neutrinos;
    backdropUniforms.uWRipples.value = weights.ripples;

    backdropUniforms.uBgPrimary.value.copy(palette.bgPrimary);
    backdropUniforms.uBgSecondary.value.copy(palette.bgSecondary);
    backdropUniforms.uFogColor.value.copy(palette.fogColor);
    backdropUniforms.uCoreColor.value.copy(palette.coreColor);

    foamUniforms.uTime.value = u;
    foamUniforms.uOpacity.value = weights.planck;
    foamUniforms.uFocusDist.value = focusDist;
    foamMesh.visible = weights.planck > 0.002;
  }

  function dispose() {
    quadGeo.dispose();
    backdropMat.dispose();
    baseQuad.dispose();
    foamGeo.dispose();
    foamMat.dispose();
  }

  return { group, update, dispose };
}
