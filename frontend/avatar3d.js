/* ═══════════════════════════════════════════════════════════════
   Avatar3D — Alex, the interviewer (polished Three.js bust)
   Public API:
     Avatar3D.init(containerId)
     Avatar3D.setState("idle" | "thinking" | "speaking" | "listening")
   ═══════════════════════════════════════════════════════════════ */
(function () {
  "use strict";

  const AVATAR = {
    _mounted: false,
    state: "idle",

    init(containerId) {
      if (this._mounted) return;
      const container = document.getElementById(containerId);
      if (!container) return;

      // Preload three.js + inject the scene module (ES module, wrapped in IIFE)
      const moduleScript = document.createElement("script");
      moduleScript.type = "module";
      moduleScript.textContent = `
import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.min.js';

(function(){
const container = document.getElementById('${containerId}');
if (!container) return;

let W = container.clientWidth  || 420;
let H = container.clientHeight || 460;

// ── Renderer ───────────────────────────────────────────────
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setSize(W, H);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
renderer.outputColorSpace = THREE.SRGBColorSpace;

const ph = container.querySelector('.avatar-placeholder');
if (ph) ph.style.display = 'none';
renderer.domElement.style.cssText = 'width:100%;height:100%;position:absolute;inset:0;';
container.appendChild(renderer.domElement);

// ── Scene & camera ─────────────────────────────────────────
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(30, W / H, 0.1, 100);
camera.position.set(0, 1.58, 5.6);
camera.lookAt(0, 1.46, 0);

// ── Lighting (3-point + rim) ───────────────────────────────
const hemi = new THREE.HemisphereLight(0xffffff, 0xcdd9ee, 0.85);
scene.add(hemi);

const key = new THREE.DirectionalLight(0xffffff, 2.0);
key.position.set(2.4, 4.2, 3.2);
key.castShadow = true;
key.shadow.mapSize.set(1024, 1024);
key.shadow.camera.near = 0.5;
key.shadow.camera.far = 20;
key.shadow.bias = -0.0004;
key.shadow.radius = 6;
scene.add(key);

const fill = new THREE.DirectionalLight(0xbcd4ff, 0.6);
fill.position.set(-3, 2, 2);
scene.add(fill);

const rim = new THREE.DirectionalLight(0x8ab4ff, 1.2);
rim.position.set(-1.5, 3, -3);
scene.add(rim);

// ── Materials ──────────────────────────────────────────────
const skinMat  = new THREE.MeshStandardMaterial({ color: 0xe8b48f, roughness: 0.62, metalness: 0.0 });
const hairMat  = new THREE.MeshStandardMaterial({ color: 0x27201b, roughness: 0.55, metalness: 0.05 });
const suitMat  = new THREE.MeshStandardMaterial({ color: 0x24344f, roughness: 0.7,  metalness: 0.05 });
const suitMat2 = new THREE.MeshStandardMaterial({ color: 0x1b2942, roughness: 0.72, metalness: 0.05 });
const shirtMat = new THREE.MeshStandardMaterial({ color: 0xf4f7fb, roughness: 0.6 });
const tieMat   = new THREE.MeshStandardMaterial({ color: 0x2563eb, roughness: 0.45, metalness: 0.1 });
const eyeWhite = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.3 });
const irisMat  = new THREE.MeshStandardMaterial({ color: 0x3a2a1a, roughness: 0.25 });
const browMat  = new THREE.MeshStandardMaterial({ color: 0x241c16, roughness: 0.6 });
const lipMat   = new THREE.MeshStandardMaterial({ color: 0xbf6a5a, roughness: 0.5 });
const glassFrame = new THREE.MeshStandardMaterial({ color: 0x1f2937, roughness: 0.4, metalness: 0.3 });

// ── Character root ─────────────────────────────────────────
const person = new THREE.Group();
scene.add(person);

// Shoulders / suit bust (lathe for a smooth rounded torso)
const shoulderPts = [];
for (let i = 0; i <= 12; i++) {
  const tt = i / 12;
  const y = tt * 0.95;
  const r = 0.86 * Math.sqrt(1 - Math.pow(tt - 0.02, 2) * 0.55) * (1 - tt * 0.18);
  shoulderPts.push(new THREE.Vector2(Math.max(0.05, r), y));
}
const torsoGeo = new THREE.LatheGeometry(shoulderPts, 48);
const torso = new THREE.Mesh(torsoGeo, suitMat);
torso.position.y = 0.48;
torso.scale.set(1.08, 1.0, 0.82);
torso.castShadow = true; torso.receiveShadow = true;
person.add(torso);

// Suit lapels (two slim angled boxes)
const lapelGeo = new THREE.BoxGeometry(0.14, 0.5, 0.05);
const lapelL = new THREE.Mesh(lapelGeo, suitMat2);
lapelL.position.set(-0.17, 1.02, 0.63); lapelL.rotation.z = 0.28; lapelL.rotation.x = -0.1;
person.add(lapelL);
const lapelR = lapelL.clone(); lapelR.position.x = 0.17; lapelR.rotation.z = -0.28; person.add(lapelR);

// Shirt triangle (small V of white between the lapels)
const shirt = new THREE.Mesh(new THREE.ConeGeometry(0.16, 0.34, 3), shirtMat);
shirt.position.set(0, 1.12, 0.6); shirt.rotation.x = Math.PI; shirt.rotation.y = Math.PI/6;
person.add(shirt);

// Collar flaps (two small angled white boxes)
const collarGeo = new THREE.BoxGeometry(0.17, 0.09, 0.04);
const collarL = new THREE.Mesh(collarGeo, shirtMat);
collarL.position.set(-0.11, 1.27, 0.6); collarL.rotation.z = 0.5;
person.add(collarL);
const collarR = collarL.clone(); collarR.position.x = 0.11; collarR.rotation.z = -0.5; person.add(collarR);

// Tie
const tieKnot = new THREE.Mesh(new THREE.BoxGeometry(0.085, 0.09, 0.05), tieMat);
tieKnot.position.set(0, 1.23, 0.64); person.add(tieKnot);
const tieBody = new THREE.Mesh(new THREE.ConeGeometry(0.075, 0.42, 4), tieMat);
tieBody.position.set(0, 0.95, 0.63); tieBody.rotation.x = -0.05; tieBody.rotation.y = Math.PI/4;
person.add(tieBody);

// Neck
const neck = new THREE.Mesh(new THREE.CylinderGeometry(0.17, 0.2, 0.3, 24), skinMat);
neck.position.y = 1.32; neck.castShadow = true;
person.add(neck);

// ── Head group ─────────────────────────────────────────────
const head = new THREE.Group();
head.position.y = 1.62;
person.add(head);

const skull = new THREE.Mesh(new THREE.SphereGeometry(0.42, 48, 48), skinMat);
skull.scale.set(0.95, 1.08, 0.98);
skull.castShadow = true;
head.add(skull);

// Jaw (slightly smaller sphere lower) for a face shape
const jaw = new THREE.Mesh(new THREE.SphereGeometry(0.34, 32, 32), skinMat);
jaw.position.set(0, -0.14, 0.03); jaw.scale.set(0.95, 0.85, 0.92);
head.add(jaw);

// Ears
const earGeo = new THREE.SphereGeometry(0.075, 16, 16);
const earL = new THREE.Mesh(earGeo, skinMat); earL.position.set(-0.4, -0.02, 0); earL.scale.set(0.7,1,0.6); head.add(earL);
const earR = earL.clone(); earR.position.x = 0.4; head.add(earR);

// Hair — cap covering top/back of the skull (leaves forehead visible)
const hairGeo = new THREE.SphereGeometry(0.445, 48, 48, 0, Math.PI * 2, 0, Math.PI * 0.52);
const hair = new THREE.Mesh(hairGeo, hairMat);
hair.position.y = 0.06; hair.scale.set(1.0, 1.02, 1.03);
hair.castShadow = true;
head.add(hair);
// Side-swept fringe (small, above the eyebrows)
const fringe = new THREE.Mesh(new THREE.SphereGeometry(0.2, 32, 20, 0, Math.PI*2, 0, Math.PI*0.45), hairMat);
fringe.position.set(0.05, 0.27, 0.3); fringe.scale.set(1.5, 0.6, 0.7); fringe.rotation.x = 0.7; fringe.rotation.z = 0.15;
head.add(fringe);

// Eyebrows
const browGeo = new THREE.BoxGeometry(0.15, 0.028, 0.05);
const browL = new THREE.Mesh(browGeo, browMat); browL.position.set(-0.16, 0.1, 0.37); browL.rotation.z = -0.05;
head.add(browL);
const browR = browL.clone(); browR.position.x = 0.16; browR.rotation.z = 0.05; head.add(browR);

// Eyes (white + iris + pupil) grouped so we can blink/move
function makeEye(x) {
  const g = new THREE.Group();
  const white = new THREE.Mesh(new THREE.SphereGeometry(0.075, 24, 24), eyeWhite);
  white.scale.set(1, 0.8, 0.6);
  g.add(white);
  const iris = new THREE.Mesh(new THREE.SphereGeometry(0.042, 20, 20), irisMat);
  iris.position.z = 0.045; iris.scale.set(1,1,0.5);
  g.add(iris);
  const pupil = new THREE.Mesh(new THREE.SphereGeometry(0.02, 16, 16), new THREE.MeshStandardMaterial({color:0x000000, roughness:0.2}));
  pupil.position.z = 0.062; g.add(pupil);
  const glint = new THREE.Mesh(new THREE.SphereGeometry(0.009, 8, 8), new THREE.MeshStandardMaterial({color:0xffffff, roughness:0.1}));
  glint.position.set(0.016, 0.016, 0.07); g.add(glint);
  g.position.set(x, 0.02, 0.35);
  return g;
}
const eyeL = makeEye(-0.16); head.add(eyeL);
const eyeR = makeEye(0.16);  head.add(eyeR);

// Glasses (thin round frames + bridge)
const glassesGrp = new THREE.Group();
const ringGeo = new THREE.TorusGeometry(0.1, 0.012, 10, 28);
const ringL = new THREE.Mesh(ringGeo, glassFrame); ringL.position.set(-0.16, 0.02, 0.4);
const ringR = new THREE.Mesh(ringGeo, glassFrame); ringR.position.set(0.16, 0.02, 0.4);
const bridge = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.012, 0.012), glassFrame); bridge.position.set(0,0.03,0.42);
const templeL = new THREE.Mesh(new THREE.BoxGeometry(0.012,0.012,0.22), glassFrame); templeL.position.set(-0.27,0.03,0.33);
const templeR = templeL.clone(); templeR.position.x = 0.27;
glassesGrp.add(ringL, ringR, bridge, templeL, templeR);
head.add(glassesGrp);

// Nose
const nose = new THREE.Mesh(new THREE.SphereGeometry(0.05, 16, 16), skinMat);
nose.position.set(0, -0.06, 0.42); nose.scale.set(0.8,1.1,1);
head.add(nose);

// Mouth (scaled on speaking)
const mouth = new THREE.Mesh(new THREE.CapsuleGeometry(0.02, 0.14, 6, 12), lipMat);
mouth.rotation.z = Math.PI/2;
mouth.position.set(0, -0.2, 0.38);
head.add(mouth);

// ── Soft contact shadow platform ───────────────────────────
const ground = new THREE.Mesh(
  new THREE.CircleGeometry(1.7, 48),
  new THREE.ShadowMaterial({ opacity: 0.18 })
);
ground.rotation.x = -Math.PI / 2;
ground.position.y = 0.18;
ground.receiveShadow = true;
scene.add(ground);

// ── Animation ──────────────────────────────────────────────
let state = 'idle';
let t = 0, blinkT = 0, blinkPhase = 0, speakT = 0;
const clock = new THREE.Clock();

window.__avatar3d_setState = function (s) { state = s; };
window.__avatar3d_resize = function () {
  W = container.clientWidth || W; H = container.clientHeight || H;
  renderer.setSize(W, H);
  camera.aspect = W / H; camera.updateProjectionMatrix();
};
const ro = new ResizeObserver(() => window.__avatar3d_resize());
ro.observe(container);

function lerp(a, b, n) { return a + (b - a) * n; }

function animate() {
  requestAnimationFrame(animate);
  const dt = Math.min(clock.getDelta(), 0.05);
  t += dt;

  // Blink
  blinkT += dt;
  if (blinkPhase === 0 && blinkT > 3.2 + Math.sin(t) * 0.8) { blinkPhase = 1; blinkT = 0; }
  if (blinkPhase === 1) {
    const s = Math.max(0.1, 1 - blinkT * 14);
    eyeL.scale.y = s; eyeR.scale.y = s;
    if (s <= 0.1) blinkPhase = 2;
  } else if (blinkPhase === 2) {
    const s = Math.min(1, (eyeL.scale.y) + blinkT * 14);
    eyeL.scale.y = s; eyeR.scale.y = s;
    if (s >= 1) { blinkPhase = 0; blinkT = 0; eyeL.scale.y = 1; eyeR.scale.y = 1; }
  }

  // Breathing (always)
  const breathe = 1 + Math.sin(t * 1.1) * 0.012;
  torso.scale.y = lerp(torso.scale.y, breathe, 0.3);

  // Targets per state
  let headRX = 0, headRY = Math.sin(t * 0.5) * 0.05, headRZ = Math.sin(t * 0.35) * 0.03;
  let posZ = 0, mouthScale = 1, browY = 0, eyeLook = 0;

  if (state === 'idle') {
    headRY = Math.sin(t * 0.45) * 0.08;
    headRZ = Math.sin(t * 0.3) * 0.04;
  } else if (state === 'thinking') {
    headRX = -0.12; headRZ = 0.12;
    headRY = 0.18 + Math.sin(t * 0.8) * 0.03;
    eyeLook = 0.03; browY = 0.015;
    mouthScale = 0.6;
  } else if (state === 'speaking') {
    speakT += dt * 10;
    mouthScale = 0.6 + Math.abs(Math.sin(speakT)) * 1.4;
    headRX = Math.sin(t * 2.2) * 0.04;
    headRY = Math.sin(t * 1.4) * 0.06;
  } else if (state === 'listening') {
    posZ = 0.12; headRX = -0.1;
    headRY = Math.sin(t * 0.6) * 0.05;
    browY = 0.01;
  }

  head.rotation.x = lerp(head.rotation.x, headRX, 0.08);
  head.rotation.y = lerp(head.rotation.y, headRY, 0.08);
  head.rotation.z = lerp(head.rotation.z, headRZ, 0.08);
  person.position.z = lerp(person.position.z, posZ, 0.08);
  mouth.scale.y = lerp(mouth.scale.y, mouthScale, 0.4);
  browL.position.y = lerp(browL.position.y, 0.1 + browY, 0.1);
  browR.position.y = lerp(browR.position.y, 0.1 + browY, 0.1);
  // Eyes look (iris/pupil shift handled via eye group x offset target)
  eyeL.position.x = lerp(eyeL.position.x, -0.16 + eyeLook, 0.1);
  eyeR.position.x = lerp(eyeR.position.x,  0.16 + eyeLook, 0.1);

  renderer.render(scene, camera);
}
animate();
console.log('[Avatar3D] loaded');
})();
`;
      document.head.appendChild(moduleScript);
      this._mounted = true;
    },

    setState(state) {
      this.state = state;
      if (typeof window.__avatar3d_setState === "function") {
        window.__avatar3d_setState(state);
      }
    },
  };

  window.Avatar3D = AVATAR;
})();
