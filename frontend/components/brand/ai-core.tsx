"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef, useState } from "react";
import { useReducedMotion } from "framer-motion";
import type { Group } from "three";
import { tokens } from "@/design-system/tokens";
import { cn } from "@/lib/utils";

const NODE_COUNT = 16;
const RADIUS = 2.2;

type Vec3 = [number, number, number];

function dist(a: Vec3, b: Vec3): number {
  return Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
}

/** Deterministic fibonacci-sphere node field + nearest-neighbor edges. */
function useNetwork() {
  return useMemo(() => {
    const nodes: Vec3[] = [];
    const golden = Math.PI * (3 - Math.sqrt(5));
    for (let i = 0; i < NODE_COUNT; i++) {
      const y = 1 - (i / (NODE_COUNT - 1)) * 2;
      const r = Math.sqrt(Math.max(0, 1 - y * y));
      const theta = golden * i;
      nodes.push([Math.cos(theta) * r * RADIUS, y * RADIUS, Math.sin(theta) * r * RADIUS]);
    }
    const edges: number[] = [];
    for (const [i, a] of nodes.entries()) {
      const neighbors = nodes
        .map((b, j) => ({ j, b, d: dist(a, b) }))
        .filter((x) => x.j !== i)
        .sort((x, y) => x.d - y.d)
        .slice(0, 2);
      for (const nb of neighbors) edges.push(a[0], a[1], a[2], nb.b[0], nb.b[1], nb.b[2]);
    }
    return { nodes, positions: new Float32Array(edges) };
  }, []);
}

function Scene({ animate }: { animate: boolean }) {
  const group = useRef<Group>(null);
  const { nodes, positions } = useNetwork();

  useFrame((_, delta) => {
    if (group.current && animate) {
      group.current.rotation.y += delta * 0.12;
      group.current.rotation.x += delta * 0.02;
    }
  });

  const violet = tokens.color.brand[500];
  const violetLight = tokens.color.brand[300];

  return (
    <group ref={group}>
      <lineSegments>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[positions, 3]} />
        </bufferGeometry>
        <lineBasicMaterial color={violet} transparent opacity={0.28} />
      </lineSegments>
      {nodes.map((p, i) => (
        <mesh key={i} position={p}>
          <sphereGeometry args={[0.08 + (i % 3) * 0.025, 16, 16]} />
          <meshStandardMaterial
            color={i % 4 === 0 ? violetLight : violet}
            emissive={violet}
            emissiveIntensity={0.5}
            roughness={0.35}
            metalness={0.1}
          />
        </mesh>
      ))}
    </group>
  );
}

/**
 * The AI Core — a lightweight floating neural network. Client-only; import via
 * next/dynamic with `ssr: false`. Slowly rotates, or renders a single static
 * frame under prefers-reduced-motion. No external assets.
 */
export default function AiCore({ className }: { className?: string }) {
  const reduce = useReducedMotion() ?? false;
  const containerRef = useRef<HTMLDivElement>(null);
  const [inView, setInView] = useState(true);

  // Pause the render loop when the canvas scrolls out of view (perf).
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([entry]) => setInView(entry?.isIntersecting ?? false),
      { threshold: 0.05 }
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  const animate = !reduce && inView;

  return (
    <div ref={containerRef} className={cn("size-full", className)} aria-hidden>
      <Canvas
        dpr={[1, 1.5]}
        camera={{ position: [0, 0, 6], fov: 45 }}
        gl={{ antialias: true, alpha: true }}
        frameloop={animate ? "always" : "demand"}
      >
        <ambientLight intensity={0.7} />
        <pointLight position={[4, 4, 5]} intensity={2.4} decay={0} color={tokens.color.brand[300]} />
        <Scene animate={animate} />
      </Canvas>
    </div>
  );
}
