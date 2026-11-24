import { useEffect, useRef } from "react";

/** Live values the animation loop in Guide.tsx writes and this renderer reads every frame (no React re-render). */
export type GhostCtl = { look: number; roll: number; vx: number; vy: number; speed: number; talking: boolean };

/**
 * The ghost model ("Ghost Game Ready" by BarnusModels, CC BY 4.0) has no skeleton, so it is brought to life in the vertex shader:
 *  - the hem ripples (travelling sine waves, stronger toward the bottom),
 *  - the hem trails behind the direction of travel,
 *  - the whole body sways slowly, even when idle.
 * three.js is imported lazily so the rest of the app does not pay for it until the ghost shows up.
 */
export default function GhostView({ size, ctl, reduced, onFail }: { size: number; ctl: React.MutableRefObject<GhostCtl>; reduced: boolean; onFail: () => void }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const reducedRef = useRef(reduced);
  reducedRef.current = reduced;

  useEffect(() => {
    let raf = 0, dead = false, cleanup = () => {};
    (async () => {
      try {
        const THREE = await import("three");
        const { GLTFLoader } = await import("three/examples/jsm/loaders/GLTFLoader.js");
        if (dead || !ref.current) return;
        const renderer = new THREE.WebGLRenderer({ canvas: ref.current, alpha: true, antialias: true, powerPreference: "low-power" });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
        renderer.setSize(size, size, false);
        renderer.outputColorSpace = THREE.SRGBColorSpace;
        const scene = new THREE.Scene();
        const cam = new THREE.PerspectiveCamera(30, 1, 0.1, 50);
        cam.position.set(0, 0.02, 3.1);
        scene.add(new THREE.AmbientLight(0xffffff, 1.25));
        const key = new THREE.DirectionalLight(0xffffff, 2.2); key.position.set(2, 3, 4); scene.add(key);
        const rim = new THREE.DirectionalLight(0xbfd8ff, 1.0); rim.position.set(-3, 1, -2); scene.add(rim);

        const U = { uTime: { value: 0 }, uVel: { value: new THREE.Vector2() }, uFlutter: { value: 1 } };
        const gltf = await new GLTFLoader().loadAsync(`${import.meta.env.BASE_URL}ghost/scene.gltf`);
        if (dead) { renderer.dispose(); return; }
        gltf.scene.traverse((o) => {
          const mesh = o as import("three").Mesh;
          if (!mesh.isMesh) return;
          const mat = mesh.material as import("three").MeshStandardMaterial;
          mat.emissive = new THREE.Color(0xffffff); mat.emissiveIntensity = 0.12;   // a faint glow, so it still reads on a dark theme
          mat.onBeforeCompile = (sh) => {
            Object.assign(sh.uniforms, U);
            sh.vertexShader = sh.vertexShader
              .replace("#include <common>", "#include <common>\nuniform float uTime; uniform vec2 uVel; uniform float uFlutter;")
              .replace("#include <begin_vertex>", `#include <begin_vertex>
                // mesh-local axes: z runs from the hem (-88) to the top of the head (+40); x,y are the horizontal plane
                float h = clamp((40.0 - position.z) / 128.0, 0.0, 1.0);       // 0 at the head, 1 at the hem
                float hem = h * h;
                float ang = atan(position.y, position.x);
                float w1 = sin(uTime * 2.6 + ang * 3.0 + position.z * 0.06);
                float w2 = sin(uTime * 1.7 - ang * 5.0 + position.z * 0.09);
                transformed.x += (w1 * 3.4 + w2 * 1.6) * hem * uFlutter;
                transformed.y += (cos(uTime * 2.1 + ang * 4.0) * 3.0) * hem * uFlutter;
                transformed.z += (sin(uTime * 3.1 + ang * 6.0) * 2.4) * hem * uFlutter;      // the hem lifts and drops like cloth
                transformed.x -= uVel.x * 16.0 * hem;                                          // trails behind the movement
                transformed.y += uVel.y * 9.0 * hem;
                transformed.z += uVel.y * 8.0 * hem;
                transformed.x += sin(uTime * 1.05) * 3.0 * h;                                  // slow body sway
                transformed.y += cos(uTime * 0.8) * 2.0 * h;`);
          };
          mat.needsUpdate = true;
        });
        const pivot = new THREE.Group();
        pivot.add(gltf.scene);
        scene.add(pivot);

        let last = performance.now(), t = 0;
        const frame = (now: number) => {
          raf = requestAnimationFrame(frame);
          if (document.hidden) return;
          const dt = Math.min(0.05, (now - last) / 1000); last = now; t += dt;
          const c = ctl.current, calm = reducedRef.current;
          U.uTime.value = t;
          U.uVel.value.set(calm ? 0 : c.vx, calm ? 0 : c.vy);
          const target = calm ? 0.25 : 1 + Math.min(1.2, c.speed / 500) + (c.talking ? 0.35 : 0);
          U.uFlutter.value += (target - U.uFlutter.value) * Math.min(1, dt * 4);
          pivot.rotation.y += ((calm ? 0 : c.look) - pivot.rotation.y) * Math.min(1, dt * 5);      // turns toward what it is pointing at
          pivot.rotation.z = calm ? 0 : c.roll + Math.sin(t * 1.3) * 0.06;
          pivot.position.y = calm ? 0 : Math.sin(t * 1.6) * 0.035;
          const stretch = calm ? 0 : Math.min(0.1, c.speed / 6000);
          pivot.scale.set(1 - stretch * 0.5, 1 + stretch, 1 - stretch * 0.5);
          renderer.render(scene, cam);
        };
        raf = requestAnimationFrame(frame);
        cleanup = () => {
          cancelAnimationFrame(raf);
          scene.traverse((o) => {
            const m = o as import("three").Mesh;
            if (m.isMesh) { m.geometry.dispose(); const mt = m.material as import("three").MeshStandardMaterial; ["map", "normalMap", "metalnessMap", "roughnessMap"].forEach((k) => (mt as unknown as Record<string, { dispose?: () => void } | null>)[k]?.dispose?.()); mt.dispose(); }
          });
          renderer.dispose();
        };
      } catch {
        if (!dead) onFail();
      }
    })();
    return () => { dead = true; cancelAnimationFrame(raf); cleanup(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [size]);

  return <canvas ref={ref} width={size} height={size} aria-hidden="true" style={{ width: size, height: size, display: "block" }} />;
}

/** Shown if WebGL is unavailable: a flat ghost, still pointing and chatting. */
export function GhostFlat({ size }: { size: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" aria-hidden="true">
      <path d="M20 90V45a30 30 0 0 1 60 0v45l-8-7-8 7-8-7-8 7-8-7-8 7-8-7z" fill="#fff" stroke="#9aa6b8" strokeWidth="2" />
      <ellipse cx="40" cy="45" rx="4" ry="6" fill="#111" /><ellipse cx="60" cy="45" rx="4" ry="6" fill="#111" />
    </svg>
  );
}
