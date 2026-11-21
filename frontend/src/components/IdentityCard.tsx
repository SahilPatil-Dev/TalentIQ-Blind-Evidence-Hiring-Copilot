"use client";
/**
 * IdentityCard.tsx — where the blind review pays off.
 *
 * Before a decision, every detail is covered by a black redaction bar. When the
 * recruiter shortlists, the backend finally sends the real identity and the bars
 * slide away. Rejected candidates stay sealed forever.
 */
import { useEffect, useState } from "react";
import type { Status } from "@/lib/api";
import { Icon } from "./Icon";

const FIELDS = [
  { key: "name", label: "Name" },
  { key: "email", label: "Email" },
  { key: "phone", label: "Phone" },
  { key: "university", label: "University" },
];

interface Props {
  identity?: Record<string, string>; // only present after shortlisting
  status: Status;
  busy: boolean;
  onShortlist: () => void;
  onReject: () => void;
}

export function IdentityCard({ identity, status, busy, onShortlist, onReject }: Props) {
  // `open` flips to true shortly AFTER the identity arrives, so the bars have
  // time to be seen and then slide away.
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (!identity) {
      setOpen(false);
      return;
    }
    const timer = window.setTimeout(() => setOpen(true), 450);
    return () => window.clearTimeout(timer);
  }, [identity]);

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
              <span className="id-text">{identity ? identity[field.key] ?? "Not in résumé" : "Hidden until shortlist"}</span>
              <i className="redact-bar" style={{ "--i": index } as React.CSSProperties} />
            </span>
          </div>
        ))}
      </div>

      {status === "NEEDS_REVIEW" && (
        <>
          <p className="id-note">
            Review the evidence first. Shortlisting reveals who this is; the decision is yours, not the AI&apos;s.
          </p>
          <button className="btn btn-primary btn-block" disabled={busy} onClick={onShortlist}>
            {busy ? <span className="spinner" /> : <Icon name="unlock" size={17} />} Shortlist and reveal identity
          </button>
          <button className="btn btn-danger btn-block" style={{ marginTop: 8 }} disabled={busy} onClick={onReject}>
            Archive candidate
          </button>
        </>
      )}
      {status === "REJECTED" && <p className="id-note">Archived. Identity stays sealed for rejected candidates.</p>}
    </section>
  );
}
