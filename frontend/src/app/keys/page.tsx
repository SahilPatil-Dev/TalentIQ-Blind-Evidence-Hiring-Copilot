"use client";
/**
 * keys/page.tsx ("/keys") — encryption keys for hidden identities (admins only).
 * Rotating creates a new key; re-encrypting moves every stored identity onto it.
 */
import { useCallback, useEffect, useState } from "react";
import { ErrorNotice, LoadingBlock } from "@/components/PageState";
import { RequireRole } from "@/components/RequireRole";
import { useToast } from "@/components/Toast";
import { Topbar } from "@/components/Topbar";
import { api, type KeyReport } from "@/lib/api";
import { can } from "@/lib/roles";

export default function KeysPage() {
  const toast = useToast();
  const [report, setReport] = useState<KeyReport | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setReport(await api.getKeys());
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load keys.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function act(action: "rotate" | "reencrypt") {
    setBusy(true);
    try {
      if (action === "rotate") {
        setReport(await api.rotateKey());
        toast("success", "New key created. Re-encrypt to move existing identities onto it.");
      } else {
        const result = await api.reencrypt();
        setReport(result);
        toast("success", `${result.records_reencrypted} identity record(s) re-encrypted.`);
      }
    } catch (reason) {
      toast("error", reason instanceof Error ? reason.message : "That did not work.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <RequireRole allowed={can.admin}>
      <Topbar trail={[{ label: "Overview", href: "/" }, { label: "Keys" }]} />
      <div className="page-head">
        <div>
          <h1>Encryption keys</h1>
          <p className="sub">
            Hidden identities are encrypted with data keys. The data keys are themselves locked by a master key that never
            enters the database.
          </p>
        </div>
      </div>
      {error && <ErrorNotice message={error} onRetry={load} />}
      {!report ? (
        !error && <LoadingBlock rows={3} />
      ) : (
        <>
          {!report.master_key_configured && (
            <div className="notice notice-warn" role="status">
              <div>
                <strong>Master key is not set</strong>
                <p>Set <code>KEY_ENCRYPTION_KEY</code> in your server settings. Until then it is derived from the secret key.</p>
              </div>
            </div>
          )}
          <section className="panel">
            <div className="data-table">
              {report.keys.length === 0 && <p className="muted" style={{ padding: 22 }}>A key is created when the first résumé is uploaded.</p>}
              {report.keys.map((key) => (
                <div className="data-row" key={key.version}>
                  <div>
                    <strong>Version {key.version}</strong>
                    <span className="muted">Created {new Date(key.created_at).toLocaleDateString()}</span>
                  </div>
                  <div><span className={`tag ${key.status === "active" ? "tag-good" : "tag-mute"}`}>{key.status === "active" ? "Active" : "Retired"}</span></div>
                  <div className="num">{key.records} identity record(s)</div>
                </div>
              ))}
              {report.legacy_records > 0 && (
                <div className="data-row">
                  <div><strong>Older format</strong><span className="muted">Written before key management</span></div>
                  <div><span className="tag tag-warn">Needs re-encryption</span></div>
                  <div className="num">{report.legacy_records} identity record(s)</div>
                </div>
              )}
            </div>
          </section>
          <div className="form-actions" style={{ justifyContent: "flex-start", marginTop: 18 }}>
            <button className="btn btn-primary" disabled={busy} onClick={() => void act("rotate")}>Create new key</button>
            <button className="btn btn-ghost" disabled={busy} onClick={() => void act("reencrypt")}>Re-encrypt identities to active key</button>
          </div>
        </>
      )}
    </RequireRole>
  );
}
