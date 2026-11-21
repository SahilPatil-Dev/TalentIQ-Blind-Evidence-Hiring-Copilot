"use client";
/**
 * CountUp.tsx — a number that counts up from its previous value to `value`.
 * Used for the dashboard stats and the score. It skips the animation for
 * people who have "reduce motion" turned on in their system settings.
 *
 * Usage: <CountUp value={42} />   or   <CountUp value={7} pad={2} /> -> "07"
 */
import { useEffect, useRef, useState } from "react";

interface CountUpProps {
  value: number;
  duration?: number; // animation length in ms
  delay?: number; // wait before starting, in ms
  pad?: number; // minimum digits, e.g. pad=2 turns 7 into "07"
}

export function CountUp({ value, duration = 900, delay = 0, pad = 0 }: CountUpProps) {
  const [shown, setShown] = useState(0);
  const from = useRef(0); // where the next animation starts

  useEffect(() => {
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduceMotion) {
      setShown(value);
      from.current = value;
      return;
    }

    let frame = 0;
    const start = from.current;
    const timer = window.setTimeout(() => {
      const startedAt = performance.now();
      const tick = (now: number) => {
        const progress = Math.min((now - startedAt) / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3); // fast start, gentle finish
        setShown(Math.round(start + (value - start) * eased));
        if (progress < 1) frame = requestAnimationFrame(tick);
        else from.current = value;
      };
      frame = requestAnimationFrame(tick);
    }, delay);

    // Clean up if the component disappears mid-animation.
    return () => {
      window.clearTimeout(timer);
      cancelAnimationFrame(frame);
    };
  }, [value, duration, delay]);

  return <span className="num">{String(shown).padStart(pad, "0")}</span>;
}
