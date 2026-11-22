"use client";
/**
 * compliance/page.tsx ("/compliance") — a live self-check of the system's controls.
 * Items marked "Needs a person" cannot be checked by software.
 * This is an engineering checklist, not legal advice.
 */
import { useCallback, useEffect, useState } from "react";
import { ErrorNotice, LoadingBlock } from "@/components/PageState";
import { RequireRole } from "@/components/RequireRole";
import { Topbar } from "@/components/Topbar";
import { api, type ComplianceReport } from "@/lib/api";
import { can } from "@/lib/roles";

const LABEL = { pass: "Pass", warn: "Improve", fail: "Fix now", manual: "Needs a person" } as const;
const TONE = { pass: "tag-good", warn: "tag-warn", fail: "tag-bad", manual: "tag-mute" } as const;

export default function CompliancePage() {
  const [report, setReport] = useState<ComplianceReport | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setReport(await api.getCompliance());
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load the report.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const areas = report ? Array.from(new Set(report.checks.map((check) => check.area))) : [];

  return (
    <RequireRole allowed={can.seeGovernance}>
      <Topbar trail={[{ label: "Overview", href: "/" }, { label: "Compliance" }]} />
      <div className="page-head">
        <div>
          <h1>Compliance review</h1>
          <p className="sub">A live check of the controls this system can verify, and a list of what people must still confirm.</p>
        </div>
        <div className="head-actions">
          <button className="btn btn-ghost" onClick={() => void load()}>Re-check</button>
          <button className="btn btn-ghost" onClick={() => window.print()}>Print</button>
        </div>
      </div>
      {error && <ErrorNotice message={error} onRetry={load} />}
      {!report ? (
        !error && <LoadingBlock rows={5} />
      ) : (
        <>
          <section className="panel panel-pad summary-row">
            {(Object.keys(LABEL) as (keyof typeof LABEL)[]).map((status) => (
              <div key={status}>
                <strong className="num">{report.counts[status]}</strong>
                <span className={`tag ${TONE[status]}`}>{LABEL[status]}</span>
              </div>
            ))}
          </section>
          {areas.map((area) => (
            <section className="panel" key={area} style={{ marginTop: 18 }}>
              <div className="panel-pad" style={{ paddingBottom: 0 }}><div className="panel-head"><h2>{area}</h2></div></div>
              <div className="data-table">
                {report.checks.filter((check) => check.area === area).map((check) => (
                  <div className="check-row" key={check.id}>
                    <span className={`tag ${TONE[check.status]}`}>{LABEL[check.status]}</span>
                    <div>
                      <strong>{check.title}</strong>
                      <span className="muted">{check.detail}</span>
                    </div>
                    <span className="muted ref">{check.reference}</span>
                  </div>
                ))}
              </div>
            </section>
          ))}
          <p className="muted" style={{ marginTop: 18 }}>{report.disclaimer} Generated {new Date(report.generated_at).toLocaleString()}.</p>
        </>
      )}
    </RequireRole>
  );
}
