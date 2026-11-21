"use client";
/**
 * RedactionDemo.tsx — the animated résumé on the dashboard hero. It plays what
 * TalentIQ does, in about 3 seconds:
 *   1. black bars cover the name, email and university (blind review)
 *   2. each skill sentence is highlighted like evidence in a marker pen
 *   3. every highlight earns points, and the score counts up
 * Click "Replay" to watch it again. (It is a made-up sample résumé.)
 *
 * The timing comes from the CSS variable --d (delay in seconds) on each piece.
 */
import { useState } from "react";
import { CountUp } from "./CountUp";

// Every line below is fictional sample text.
const EVIDENCE = [
  { text: "Built a Django REST API for internal tools.", label: "Python backend", points: 40, at: 1.7 },
  { text: "Developed AI agents with LangGraph and RAG.", label: "AI agents", points: 35, at: 2.5 },
  { text: "Deployed PostgreSQL and Redis services using Docker.", label: "System design", points: 25, at: 3.3 },
];

export function RedactionDemo() {
  const [run, setRun] = useState(0); // changing this restarts every animation

  return (
    <div className="demo">
      <div className="doc" key={run}>
        <div className="doc-head">
          <span className="redact" style={{ "--d": "0.5s" } as React.CSSProperties}>
            Avery Morgan
            <i />
          </span>
          <span className="redact" style={{ "--d": "0.8s" } as React.CSSProperties}>
            avery@example.test
            <i />
          </span>
          <span className="redact" style={{ "--d": "1.1s" } as React.CSSProperties}>
            Northfield University
            <i />
          </span>
        </div>

        {EVIDENCE.map((item) => (
          <div key={item.label} className="doc-line">
            <span className="mark" style={{ "--d": `${item.at}s` } as React.CSSProperties}>
              {item.text}
            </span>
            <span className="doc-chip" style={{ "--d": `${item.at + 0.35}s` } as React.CSSProperties}>
              {item.label} <b>+{item.points}</b>
            </span>
          </div>
        ))}

        <div className="doc-score">
          <span>Score</span>
          <strong>
            <CountUp value={100} duration={900} delay={3900} />
          </strong>
        </div>
      </div>
      <button className="replay" onClick={() => setRun((n) => n + 1)}>
        Replay sample
      </button>
    </div>
  );
}
