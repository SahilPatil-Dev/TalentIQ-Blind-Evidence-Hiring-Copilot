"use client";
/**
 * ScoreRing.tsx — the circular score gauge on a candidate's page.
 * The ring draws itself from 0 to the score (a CSS transition on the SVG
 * stroke), and the number counts up at the same time.
 */
import { useEffect, useState } from "react";
import { scoreTone } from "@/lib/format";
import { CountUp } from "./CountUp";

const RADIUS = 54;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

export function ScoreRing({ value, size = 128 }: { value: number; size?: number }) {
  // Start empty, then fill on the next tick so the CSS transition can play.
  const [drawn, setDrawn] = useState(0);
  useEffect(() => {
    const timer = window.setTimeout(() => setDrawn(value), 150);
    return () => window.clearTimeout(timer);
  }, [value]);

  return (
    <div className={`ring ring-${scoreTone(value)}`} style={{ width: size, height: size }}>
      <svg viewBox="0 0 132 132" aria-hidden="true">
        <circle className="ring-track" cx="66" cy="66" r={RADIUS} />
        <circle
          className="ring-fill"
          cx="66"
          cy="66"
          r={RADIUS}
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={CIRCUMFERENCE * (1 - drawn / 100)}
          transform="rotate(-90 66 66)"
        />
      </svg>
      <div className="ring-label" role="img" aria-label={`Score ${value} out of 100`}>
        <strong>
          <CountUp value={value} duration={1100} delay={150} />
        </strong>
        <span>out of 100</span>
      </div>
    </div>
  );
}
