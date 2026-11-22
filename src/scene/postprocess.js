import * as THREE from 'three';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';
import { ShaderPass } from 'three/examples/jsm/postprocessing/ShaderPass.js';

const COMPOSITE_SHADER = {
  uniforms: {
    tDiffuse: { value: null },
    uResolution: { value: new THREE.Vector2(1280, 720) },
    uTime: { value: 0 },
    uCoreUv: { value: new THREE.Vector2(0.5, 0.5) },
    uCoreWeight: { value: 1.0 },
    uShimmerStrength: { value: 1.0 },
    uDofStrength: { value: 0.45 },
    uGrainIntensity: { value: 0.022 }
  },
  vertexShader: /* glsl */ `
    varying vec2 vUv;
    void main() {
      vUv = uv;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }
  `,
  fragmentShader: /* glsl */ `
    precision highp float;

    uniform sampler2D tDiffuse;
    uniform vec2 uResolution;
    uniform float uTime;
    uniform vec2 uCoreUv;
    uniform float uCoreWeight;
    uniform float uShimmerStrength;
    uniform float uDofStrength;
    uniform float uGrainIntensity;

    varying vec2 vUv;

    float hash12(vec2 p) {
      vec3 p3 = fract(vec3(p.xyx) * 0.1031);
      p3 += dot(p3, p3.yzx + 33.33);
      return fract((p3.x + p3.y) * p3.z);
    }

    vec3 acesFilmic(vec3 x) {
      float a = 2.51;
      float b = 0.03;
      float c = 2.43;
      float d = 0.59;
      float e = 0.14;
      return clamp((x * (a * x + b)) / (x * (c * x + d) + e), 0.0, 1.0);
    }

    vec3 linearToSrgb(vec3 lin) {
      vec3 lo = lin * 12.92;
      vec3 hi = 1.055 * pow(max(lin, vec3(0.0)), vec3(1.0 / 2.4)) - 0.055;
      return mix(lo, hi, step(vec3(0.0031308), lin));
    }

    void main() {
      vec2 uv = vUv;
      float aspect = uResolution.x / max(uResolution.y, 1.0);

      // 1. Heat-shimmer UV distortion around the projected primordial core
      vec2 toCore = uv - uCoreUv;
      toCore.x *= aspect;
      float coreDist = length(toCore);
      float shimmerZone = exp(-coreDist * coreDist * 5.2) * uCoreWeight * uShimmerStrength;

      if (shimmerZone > 0.001) {
        float wave1 = sin(uv.y * 38.0 - uTime * 9.5 + uv.x * 18.0);
        float wave2 = cos(uv.x * 32.0 + uTime * 7.8 - uv.y * 22.0);
        vec2 offset = vec2(wave1, wave2) * 0.0042 * shimmerZone;
        uv = clamp(uv + offset, vec2(0.001), vec2(0.999));
      }

      // 2. Subtle optical lens Depth-of-Field (8-tap rotated Poisson disc weighted toward screen edges)
      vec2 centerVec = uv - 0.5;
      float edgeFactor = smoothstep(0.18, 0.78, length(centerVec * vec2(aspect, 1.0)));
      float blurRadius = (0.0005 + 0.0022 * edgeFactor) * uDofStrength;

      vec3 hdr = texture2D(tDiffuse, uv).rgb;

      if (blurRadius > 0.0002) {
        vec2 texel = blurRadius / vec2(aspect, 1.0);
        float rot = hash12(gl_FragCoord.xy + fract(uTime * 17.3)) * 6.283185;
        float sr = sin(rot);
        float cr = cos(rot);
        mat2 rotMat = mat2(cr, -sr, sr, cr);

        const vec2 taps[8] = vec2[8](
          vec2(-0.707, -0.707),
          vec2( 0.707, -0.707),
          vec2(-0.707,  0.707),
          vec2( 0.707,  0.707),
          vec2( 0.000, -1.000),
          vec2( 0.000,  1.000),
          vec2(-1.000,  0.000),
          vec2( 1.000,  0.000)
        );

        vec3 accum = hdr;
        for (int i = 0; i < 8; i++) {
          vec2 sampleUv = clamp(uv + (rotMat * taps[i]) * texel, vec2(0.001), vec2(0.999));
          accum += texture2D(tDiffuse, sampleUv).rgb;
        }
        hdr = accum / 9.0;
      }

      // 3. Subtle chromatic aberration in intense heat-shimmer zone
      if (shimmerZone > 0.02) {
        vec2 caOffset = normalize(toCore + vec2(1e-5)) * 0.0018 * shimmerZone;
        caOffset.x /= aspect;
        hdr.r = mix(hdr.r, texture2D(tDiffuse, clamp(uv + caOffset, 0.001, 0.999)).r, 0.45);
        hdr.b = mix(hdr.b, texture2D(tDiffuse, clamp(uv - caOffset, 0.001, 0.999)).b, 0.45);
      }

      // 4. ACES Filmic Tonemapping + exact sRGB encoding
      vec3 mapped = acesFilmic(hdr * 0.95);
      vec3 srgb = linearToSrgb(mapped);

      // 5. Subtle deterministic animated documentary film grain
      float grain = hash12(gl_FragCoord.xy + vec2(fract(uTime * 19.7) * 517.0, fract(uTime * 31.3) * 389.0)) - 0.5;
      srgb = clamp(srgb + grain * uGrainIntensity, 0.0, 1.0);

      gl_FragColor = vec4(srgb, 1.0);
    }
  `
};

export function createPostPipeline(renderer, scene, camera, width, height) {
  const rt = new THREE.WebGLRenderTarget(width, height, {
    type: THREE.HalfFloatType,
    format: THREE.RGBAFormat,
    minFilter: THREE.LinearFilter,
    magFilter: THREE.LinearFilter
  });

  const composer = new EffectComposer(renderer, rt);
  composer.setPixelRatio(1);
  composer.setSize(width, height);

  const renderPass = new RenderPass(scene, camera);
  composer.addPass(renderPass);

  const bloomPass = new UnrealBloomPass(
    new THREE.Vector2(width, height),
    0.55,
    0.50,
    1.12
  );
  composer.addPass(bloomPass);

  const compositePass = new ShaderPass(COMPOSITE_SHADER);
  compositePass.renderToScreen = true;
  composer.addPass(compositePass);

  function setSize(w, h) {
    composer.setPixelRatio(1);
    composer.setSize(w, h);
    bloomPass.resolution.set(w, h);
    compositePass.uniforms.uResolution.value.set(w, h);
  }

  function update(u, palette, coreUv, coreWeight) {
    bloomPass.strength = palette.bloomStrength;
    compositePass.uniforms.uTime.value = u;
    compositePass.uniforms.uCoreUv.value.copy(coreUv);
    compositePass.uniforms.uCoreWeight.value = coreWeight;
    compositePass.uniforms.uShimmerStrength.value = palette.shimmerStrength;
  }

  function render() {
    composer.render();
  }

  function dispose() {
    rt.dispose();
    bloomPass.dispose();
    composer.dispose();
  }

  return { setSize, update, render, dispose };
}
