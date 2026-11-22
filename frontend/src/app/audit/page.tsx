"use client";
/** audit/page.tsx ("/audit") — who did what, plus a check that the log was not tampered with. */
import { useCallback, useEffect, useState } from "react";
import { ErrorNotice, LoadingBlock } from "@/components/PageState";
import { RequireRole } from "@/components/RequireRole";
import { useToast } from "@/components/Toast";
import { Topbar } from "@/components/Topbar";
import { api, type AuditEntry } from "@/lib/api";
import { can } from "@/lib/roles";

const FILTERS = [
  { value: "", label: "All events" },
  { value: "identity.reveal", label: "Identity reveals" },
  { value: "application.shortlist", label: "Shortlists" },
  { value: "application.reject", label: "Rejections" },
  { value: "application.delete", label: "Deletions" },
  { value: "retention.run", label: "Retention runs" },
  { value: "key.rotate", label: "Key rotations" },
  { value: "user.login_failed", label: "Failed sign-ins" },
];

export default function AuditPage() {
  const toast = useToast();
  const [entries, setEntries] = useState<AuditEntry[] | null>(null);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState("");
  const [verdict, setVerdict] = useState<{ valid: boolean; checked: number; first_bad_id: number | null } | null>(null);

  const load = useCallback(async () => {
    try {
      setEntries(await api.getAudit(filter));
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load the audit log.");
    }
  }, [filter]);

  useEffect(() => {
    void load();
  }, [load]);

  async function verify() {
    try {
      setVerdict(await api.verifyAudit());
    } catch (reason) {
      toast("error", reason instanceof Error ? reason.message : "Could not verify the log.");
    }
  }

  return (
    <RequireRole allowed={can.seeGovernance}>
      <Topbar trail={[{ label: "Overview", href: "/" }, { label: "Audit log" }]} />
      <div className="page-head">
        <div>
          <h1>Audit log</h1>
          <p className="sub">Every sign-in, decision, identity reveal and deletion. Entries are chained so edits can be detected.</p>
        </div>
        <div className="head-actions">
          <button className="btn btn-ghost" onClick={() => void verify()}>Verify integrity</button>
          <button className="btn btn-ghost" onClick={() => void api.downloadAuditCsv().catch((e: Error) => toast("error", e.message))}>Export CSV</button>
        </div>
      </div>

      {verdict && (
        <div className={`notice ${verdict.valid ? "notice-ok" : "notice-error"}`} role="status">
          <div>
            <strong>{verdict.valid ? "Log is intact" : "Log has been altered"}</strong>
            <p>
              {verdict.valid
                ? `${verdict.checked} entries verified.`
                : `The chain breaks at entry ${verdict.first_bad_id}. Treat this as a security incident.`}
            </p>
          </div>
        </div>
      )}

      <div className="toolbar">
        <select className="input" aria-label="Filter events" value={filter} onChange={(e) => setFilter(e.target.value)}>
          {FILTERS.map((item) => (
            <option key={item.value} value={item.value}>{item.label}</option>
          ))}
        </select>
      </div>

      {error && <ErrorNotice message={error} onRetry={load} />}
      {!entries ? (
        !error && <LoadingBlock rows={5} />
      ) : (
        <section className="panel">
          <div className="audit-list">
            {entries.length === 0 && <p className="muted" style={{ padding: 22 }}>No events yet.</p>}
            {entries.map((entry) => (
              <div className="audit-row" key={entry.id}>
                <div className="num muted">{new Date(entry.at).toLocaleString()}</div>
                <div>
                  <strong>{entry.action}</strong>
                  <span className="muted">{entry.actor || "system"}{entry.target_type ? ` · ${entry.target_type} ${entry.target_id}` : ""}</span>
                </div>
                <code className="detail">{Object.keys(entry.detail).length ? JSON.stringify(entry.detail) : ""}</code>
              </div>
            ))}
          </div>
        </section>
      )}
    </RequireRole>
  );
}
