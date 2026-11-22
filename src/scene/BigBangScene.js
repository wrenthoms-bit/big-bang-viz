import * as THREE from 'three';
import {
  getCameraState,
  getStageWeights,
  getEpochPalette,
  clamp
} from '../timeline.js';
import { createPlasmaBackdrop } from './plasmaBackdrop.js';
import { createInflationLattice } from './inflationLattice.js';
import { createQuarkGluonPlasma } from './quarkGluonPlasma.js';
import { createHadronization } from './hadronization.js';
import { createAnnihilation } from './annihilation.js';
import { createNeutrinos } from './neutrinos.js';
import { createPostPipeline } from './postprocess.js';

export function createBigBangScene(canvas) {
  const renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: false,
    alpha: false,
    powerPreference: 'high-performance',
    preserveDrawingBuffer: false
  });
  renderer.toneMapping = THREE.NoToneMapping;
  renderer.outputColorSpace = THREE.LinearSRGBColorSpace;
  renderer.autoClear = true;

  const scene = new THREE.Scene();

  const initW = Math.max(1, window.innerWidth);
  const initH = Math.max(1, window.innerHeight);
  const camera = new THREE.PerspectiveCamera(68, initW / initH, 0.1, 450);

  // Instantiate all 6 epoch layers + volumetric opaque plasma backdrop
  const plasmaBackdrop = createPlasmaBackdrop();
  const inflationLattice = createInflationLattice();
  const quarkGluonPlasma = createQuarkGluonPlasma();
  const hadronization = createHadronization();
  const annihilation = createAnnihilation();
  const neutrinos = createNeutrinos();

  scene.add(plasmaBackdrop.group);
  scene.add(inflationLattice.group);
  scene.add(quarkGluonPlasma.group);
  scene.add(hadronization.group);
  scene.add(annihilation.group);
  scene.add(neutrinos.group);

  const dprCap = Math.min(window.devicePixelRatio || 1, 1.5);
  let renderW = Math.round(initW * dprCap);
  let renderH = Math.round(initH * dprCap);
  let isFixedResolution = false;

  renderer.setPixelRatio(1);
  renderer.setSize(renderW, renderH, false);

  const post = createPostPipeline(renderer, scene, camera, renderW, renderH);

  function resizeToViewport() {
    if (isFixedResolution) return;
    const w = Math.max(1, window.innerWidth);
    const h = Math.max(1, window.innerHeight);
    const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    renderW = Math.round(w * dpr);
    renderH = Math.round(h * dpr);

    camera.aspect = w / h;
    camera.updateProjectionMatrix();

    renderer.setPixelRatio(1);
    renderer.setSize(renderW, renderH, false);
    post.setSize(renderW, renderH);
  }

  function setFixedResolution(width, height) {
    isFixedResolution = true;
    renderW = width;
    renderH = height;

    camera.aspect = width / height;
    camera.updateProjectionMatrix();

    renderer.setPixelRatio(1);
    renderer.setSize(width, height, false);
    post.setSize(width, height);
  }

  function restoreViewportResolution() {
    isFixedResolution = false;
    resizeToViewport();
  }

  const _origin = new THREE.Vector3(0, 0, 0);
  const _proj = new THREE.Vector3();
  const _camDir = new THREE.Vector3();
  const _toOrigin = new THREE.Vector3();
  const _coreUv = new THREE.Vector2(0.5, 0.5);

  function renderAt(u) {
    const camState = getCameraState(u);
    camera.position.copy(camState.position);
    if (camera.fov !== camState.fov) {
      camera.fov = camState.fov;
      camera.updateProjectionMatrix();
    }
    camera.lookAt(camState.target);
    camera.updateMatrixWorld();

    const weights = getStageWeights(u);
    const palette = getEpochPalette(u);

    // Update all epoch layers
    plasmaBackdrop.update(u, camera, weights, palette, camState.focusDist);
    inflationLattice.update(u, camera, weights, palette, camState.focusDist);
    quarkGluonPlasma.update(u, camera, weights, palette, camState.focusDist);
    hadronization.update(u, camera, weights, palette, camState.focusDist);
    annihilation.update(u, camera, weights, palette, camState.focusDist);
    neutrinos.update(u, camera, weights, palette, camState.focusDist);

    // Compute projected screen UV of core (0,0,0) for subtle heat shimmer
    _proj.copy(_origin).project(camera);
    _coreUv.set(_proj.x * 0.5 + 0.5, _proj.y * 0.5 + 0.5);

    camera.getWorldDirection(_camDir);
    _toOrigin.copy(_origin).sub(camera.position).normalize();
    const coreWeight = clamp(_camDir.dot(_toOrigin), 0, 1);

    post.update(u, palette, _coreUv, coreWeight);
    post.render();
  }

  function dispose() {
    plasmaBackdrop.dispose();
    inflationLattice.dispose();
    quarkGluonPlasma.dispose();
    hadronization.dispose();
    annihilation.dispose();
    neutrinos.dispose();
    post.dispose();
    renderer.dispose();
  }

  return {
    renderer,
    scene,
    camera,
    renderAt,
    resizeToViewport,
    setFixedResolution,
    restoreViewportResolution,
    dispose
  };
}
