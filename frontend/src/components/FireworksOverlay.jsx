import React, { useEffect, useRef, useState, useCallback } from 'react';

/**
 * FireworksOverlay — Canvas-based particle celebration effect.
 * Triggered when the CogniGuard protection pipeline completes successfully.
 *
 * Props:
 *   visible: boolean — whether to show the overlay
 *   onDismiss: () => void — callback to close the overlay
 */

const COLORS = [
  '#3b82f6', '#60a5fa', '#10b981', '#34d399',
  '#f59e0b', '#fbbf24', '#8b5cf6', '#c084fc',
  '#ef4444', '#f87171', '#ec4899', '#ffffff',
];

const PARTICLE_COUNT = 80;
const BURST_COUNT = 6;
const GRAVITY = 0.04;
const FRICTION = 0.985;
const FADE_RATE = 0.012;

function randomInRange(min, max) {
  return Math.random() * (max - min) + min;
}

function createBurst(x, y) {
  const particles = [];
  for (let i = 0; i < PARTICLE_COUNT; i++) {
    const angle = (Math.PI * 2 * i) / PARTICLE_COUNT + randomInRange(-0.15, 0.15);
    const speed = randomInRange(1.5, 5.5);
    particles.push({
      x,
      y,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed,
      alpha: 1,
      color: COLORS[Math.floor(Math.random() * COLORS.length)],
      size: randomInRange(1.5, 3.5),
      decay: randomInRange(0.008, 0.018),
    });
  }
  return particles;
}

export default function FireworksOverlay({ visible, onDismiss }) {
  const canvasRef = useRef(null);
  const animRef = useRef(null);
  const particlesRef = useRef([]);
  const [showBanner, setShowBanner] = useState(false);

  const stop = useCallback(() => {
    if (animRef.current) {
      cancelAnimationFrame(animRef.current);
      animRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!visible) {
      stop();
      setShowBanner(false);
      return;
    }

    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;

    function resize() {
      canvas.width = window.innerWidth * dpr;
      canvas.height = window.innerHeight * dpr;
      canvas.style.width = `${window.innerWidth}px`;
      canvas.style.height = `${window.innerHeight}px`;
      ctx.scale(dpr, dpr);
    }
    resize();
    window.addEventListener('resize', resize);

    // Schedule bursts
    const w = window.innerWidth;
    const h = window.innerHeight;
    particlesRef.current = [];

    for (let i = 0; i < BURST_COUNT; i++) {
      setTimeout(() => {
        const bx = randomInRange(w * 0.15, w * 0.85);
        const by = randomInRange(h * 0.15, h * 0.55);
        particlesRef.current.push(...createBurst(bx, by));
      }, i * 450 + randomInRange(0, 200));
    }

    // Show banner after 1.5s
    const bannerTimer = setTimeout(() => setShowBanner(true), 1500);
    // Auto-dismiss after 5s
    const dismissTimer = setTimeout(() => {
      if (onDismiss) onDismiss();
    }, 5000);

    function animate() {
      const { innerWidth: cw, innerHeight: ch } = window;
      ctx.clearRect(0, 0, cw, ch);

      const particles = particlesRef.current;
      for (let i = particles.length - 1; i >= 0; i--) {
        const p = particles[i];
        p.vy += GRAVITY;
        p.vx *= FRICTION;
        p.vy *= FRICTION;
        p.x += p.vx;
        p.y += p.vy;
        p.alpha -= p.decay;

        if (p.alpha <= 0) {
          particles.splice(i, 1);
          continue;
        }

        ctx.save();
        ctx.globalAlpha = p.alpha;
        ctx.fillStyle = p.color;
        ctx.shadowColor = p.color;
        ctx.shadowBlur = p.size * 3;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      }

      animRef.current = requestAnimationFrame(animate);
    }

    animRef.current = requestAnimationFrame(animate);

    return () => {
      stop();
      window.removeEventListener('resize', resize);
      clearTimeout(bannerTimer);
      clearTimeout(dismissTimer);
    };
  }, [visible, onDismiss, stop]);

  if (!visible) return null;

  return (
    <div className="fireworks-overlay" onClick={onDismiss}>
      <canvas ref={canvasRef} className="fireworks-canvas" />
      {showBanner && (
        <div className="fireworks-banner">
          <div className="fireworks-banner-icon">✅</div>
          <h2 className="fireworks-banner-title">防护流程执行完毕</h2>
          <p className="fireworks-banner-sub">
            Protection Pipeline Completed Successfully
          </p>
          <span className="fireworks-banner-dismiss">点击任意位置关闭 / Click anywhere to dismiss</span>
        </div>
      )}
    </div>
  );
}
