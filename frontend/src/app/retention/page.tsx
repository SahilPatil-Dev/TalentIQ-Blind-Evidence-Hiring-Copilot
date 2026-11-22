"use client";
/**
 * retention/page.tsx ("/retention") — how long candidate data is kept.
 * Admins can change the limits, preview what would be deleted, and run the deletion.
 * Auditors can read it.
 */
import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { ErrorNotice, LoadingBlock } from "@/components/PageState";
import { RequireRole } from "@/components/RequireRole";
import { useToast } from "@/components/Toast";
import { Topbar } from "@/components/Topbar";
import { api, type RetentionPolicy } from "@/lib/api";
import { can } from "@/lib/roles";

const FIELDS = [
  { key: "rejected_days", label: "Rejected candidates", help: "Counted from the decision date." },
  { key: "undecided_days", label: "Not yet decided", help: "Counted from the upload date." },
  { key: "shortlisted_days", label: "Shortlisted candidates", help: "Counted from the decision date." },
] as const;

export default function RetentionPage() {
  const toast = useToast();
  const { user } = useAuth();
  const isAdmin = can.admin(user?.role);
  const [policy, setPolicy] = useState<RetentionPolicy | null>(null);
  const [draft, setDraft] = useState<Record<string, number>>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const result = await api.getRetention();
      setPolicy(result);
      setDraft({ rejected_days: result.rejected_days, undecided_days: result.undecided_days, shortlisted_days: result.shortlisted_days });
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load the policy.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function save() {
    setBusy(true);
    try {
      await api.saveRetention({
        rejected_days: draft.rejected_days,
        undecided_days: draft.undecided_days,
        shortlisted_days: draft.shortlisted_days,
      });
      await load();
      toast("success", "Retention policy saved.");
    } catch (reason) {
      toast("error", reason instanceof Error ? reason.message : "Could not save.");
    } finally {
      setBusy(false);
    }
  }

  async function run(dryRun: boolean) {
    if (!dryRun && !window.confirm("Permanently delete everything that is past its retention period?")) return;
    setBusy(true);
    try {
      const result = await api.runRetention(dryRun);
      toast("info", dryRun ? `${result.due} application(s) would be deleted.` : `${result.deleted} application(s) deleted.`);
      await load();
    } catch (reason) {
      toast("error", reason instanceof Error ? reason.message : "Could not run retention.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <RequireRole allowed={can.seeGovernance}>
      <Topbar trail={[{ label: "Overview", href: "/" }, { label: "Retention" }]} />
      <div className="page-head">
        <div>
          <h1>Retention and deletion</h1>
          <p className="sub">Candidate data is deleted automatically when it is no longer needed. Legal holds are never deleted.</p>
        </div>
      </div>
      {error && <ErrorNotice message={error} onRetry={load} />}
      {!policy ? (
        !error && <LoadingBlock rows={3} />
      ) : (
        <>
          <section className="panel panel-pad">
            <div className="panel-head"><h2>Keep candidate data for</h2></div>
            {FIELDS.map((field) => (
              <label className="field" key={field.key}>
                <span>{field.label} <small>— {field.help}</small></span>
                <div className="weight-field" style={{ maxWidth: 200 }}>
                  <input
                    className="input"
                    type="number"
                    min={1}
                    max={3650}
                    disabled={!isAdmin}
                    value={draft[field.key] ?? ""}
                    onChange={(e) => setDraft({ ...draft, [field.key]: Number(e.target.value) })}
                  />
                  <span>days</span>
                </div>
              </label>
            ))}
            {isAdmin && (
              <button className="btn btn-primary" disabled={busy} onClick={() => void save()}>Save policy</button>
            )}
          </section>

          <section className="panel panel-pad" style={{ marginTop: 20 }}>
            <div className="panel-head"><h2>Status</h2></div>
            <ul className="plain-list">
              <li><strong className="num">{policy.due_now}</strong> application(s) are past retention right now</li>
              <li><strong className="num">{policy.on_legal_hold}</strong> application(s) are on legal hold</li>
              <li>
                Last run: {policy.last_run_at ? `${new Date(policy.last_run_at).toLocaleString()} (${policy.last_run_deleted} deleted)` : "never"}
              </li>
              <li>The policy also runs every time the server starts.</li>
            </ul>
            {isAdmin && (
              <div className="form-actions" style={{ justifyContent: "flex-start" }}>
                <button className="btn btn-ghost" disabled={busy} onClick={() => void run(true)}>Preview deletion</button>
                <button className="btn btn-danger" disabled={busy} onClick={() => void run(false)}>Delete expired data now</button>
              </div>
            )}
          </section>
        </>
      )}
    </RequireRole>
  );
}
