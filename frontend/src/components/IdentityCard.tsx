"use client";
/**
 * IdentityCard.tsx — where the blind review pays off.
 *
 * Every detail is covered by a black redaction bar. Deciding needs a written reason.
 * After a shortlist, the recruiter can reveal the identity by giving a reason, which
 * is written to the audit log. Rejected candidates stay sealed forever.
 */
import { useEffect, useState } from "react";
import type { RevealEntry, Status } from "@/lib/api";
import { Icon } from "./Icon";

const FIELDS = [
  { key: "name", label: "Name" },
  { key: "email", label: "Email" },
  { key: "phone", label: "Phone" },
  { key: "university", label: "University" },
];

type Mode = "shortlist" | "reject" | "reveal";

interface Props {
  identity?: Record<string, string>; // only present after an audited reveal
  status: Status;
  busy: boolean;
  canManage: boolean; // recruiters and admins; reviewers are read-only
  history: RevealEntry[]; // who revealed this identity before, and why
  onDecide: (decision: "shortlist" | "reject", reason: string) => void;
  onReveal: (reason: string) => void;
}

const PROMPT: Record<Mode, { title: string; hint: string; button: string; min: number }> = {
  shortlist: { title: "Why shortlist?", hint: "e.g. Strong Python evidence on the API project", button: "Confirm shortlist", min: 5 },
  reject: { title: "Why archive?", hint: "e.g. No evidence for the main criteria", button: "Confirm archive", min: 5 },
  reveal: { title: "Why do you need the identity?", hint: "e.g. To schedule the interview. This is logged.", button: "Reveal identity", min: 10 },
};

export function IdentityCard({ identity, status, busy, canManage, history, onDecide, onReveal }: Props) {
  // `open` flips to true shortly AFTER the identity arrives, so the bars have
  // time to be seen and then slide away.
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<Mode | null>(null);
  const [reason, setReason] = useState("");
  useEffect(() => {
    if (!identity) {
      setOpen(false);
      return;
    }
    const timer = window.setTimeout(() => setOpen(true), 450);
    return () => window.clearTimeout(timer);
  }, [identity]);

  function confirm() {
    if (!mode) return;
    if (mode === "reveal") onReveal(reason.trim());
    else onDecide(mode, reason.trim());
    setMode(null);
    setReason("");
  }

  return (
    <section className={`panel panel-pad identity ${open ? "is-open" : ""}`}>
      <div className="panel-head">
        <h2>Identity</h2>
        <span className={`seal-tag ${open ? "open" : ""}`}>
          <Icon name={open ? "unlock" : "lock"} size={14} /> {open ? "Revealed" : "Sealed"}
        </span>
      </div>

      <div className="id-rows">
        {FIELDS.map((field, index) => (
          <div className="id-row" key={field.key}>
            <span className="id-label">{field.label}</span>
            <span className="id-value">
              <span className="id-text">{identity ? identity[field.key] ?? "Not in résumé" : "Hidden"}</span>
              <i className="redact-bar" style={{ "--i": index } as React.CSSProperties} />
            </span>
          </div>
        ))}
      </div>

      {mode && (
        <div className="reason-box">
          <label className="field" style={{ marginBottom: 10 }}>
            <span>{PROMPT[mode].title}</span>
            <textarea className="input" rows={3} autoFocus value={reason} placeholder={PROMPT[mode].hint} onChange={(e) => setReason(e.target.value)} />
          </label>
          <button className="btn btn-primary btn-block" disabled={busy || reason.trim().length < PROMPT[mode].min} onClick={confirm}>
            {busy ? <span className="spinner" /> : null} {PROMPT[mode].button}
          </button>
          <button className="btn btn-ghost btn-block" style={{ marginTop: 8 }} onClick={() => { setMode(null); setReason(""); }}>Cancel</button>
        </div>
      )}

      {!mode && canManage && status === "NEEDS_REVIEW" && (
        <>
          <p className="id-note">Review the evidence first. The decision is yours, not the AI&apos;s, and it needs a reason.</p>
          <button className="btn btn-primary btn-block" disabled={busy} onClick={() => setMode("shortlist")}>
            <Icon name="check" size={17} /> Shortlist
          </button>
          <button className="btn btn-danger btn-block" style={{ marginTop: 8 }} disabled={busy} onClick={() => setMode("reject")}>
            Archive candidate
          </button>
        </>
      )}
      {!mode && canManage && status === "SHORTLISTED" && !identity && (
        <>
          <p className="id-note">Shortlisted. Revealing the identity needs a reason and is recorded in the audit log.</p>
          <button className="btn btn-primary btn-block" disabled={busy} onClick={() => setMode("reveal")}>
            <Icon name="unlock" size={17} /> Reveal identity
          </button>
        </>
      )}
      {!canManage && <p className="id-note">Your role can review evidence but cannot decide or reveal identities.</p>}
      {status === "REJECTED" && <p className="id-note">Archived. Identity stays sealed for rejected candidates.</p>}

      {history.length > 0 && (
        <div className="reveal-history">
          <h3>Identity reveals</h3>
          <ul>
            {history.map((entry, index) => (
              <li key={index}>
                <strong>{entry.by}</strong> · {new Date(entry.at).toLocaleString()}
                <br />
                <span className="muted">&ldquo;{entry.reason}&rdquo;</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
