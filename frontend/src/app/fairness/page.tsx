"use client";
/**
 * fairness/page.tsx ("/fairness") — tests that identity cannot change a score.
 *
 * 1) Counterfactual test: the same résumé with different names, universities and
 *    pronouns must get the same score after redaction.
 * 2) Adverse impact: enter how many people from each group applied and were selected;
 *    we apply the "four-fifths" rule.
 */
import { useCallback, useEffect, useState } from "react";
import { ErrorNotice, LoadingBlock } from "@/components/PageState";
import { RequireRole } from "@/components/RequireRole";
import { useToast } from "@/components/Toast";
import { Topbar } from "@/components/Topbar";
import { api, type FairnessRun, type ImpactResult } from "@/lib/api";
import { can } from "@/lib/roles";

interface GroupDraft {
  name: string;
  applicants: string;
  selected: string;
}

export default function FairnessPage() {
  const toast = useToast();
  const [runs, setRuns] = useState<FairnessRun[] | null>(null);
  const [latest, setLatest] = useState<FairnessRun | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [groups, setGroups] = useState<GroupDraft[]>([
    { name: "Group A", applicants: "", selected: "" },
    { name: "Group B", applicants: "", selected: "" },
  ]);
  const [impact, setImpact] = useState<ImpactResult | null>(null);

  const load = useCallback(async () => {
    try {
      setRuns(await api.getFairnessRuns());
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load fairness runs.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function run() {
    setBusy(true);
    try {
      const result = await api.runFairness();
      setLatest(result);
      await load();
      toast(result.passed ? "success" : "error", result.passed ? "Fairness test passed." : "Fairness test FAILED.");
    } catch (reason) {
      toast("error", reason instanceof Error ? reason.message : "Could not run the test.");
    } finally {
      setBusy(false);
    }
  }

  async function calculate() {
    try {
      setImpact(
        await api.adverseImpact(
          groups.map((group) => ({ name: group.name, applicants: Number(group.applicants), selected: Number(group.selected) }))
        )
      );
    } catch (reason) {
      toast("error", reason instanceof Error ? reason.message : "Check the numbers.");
    }
  }

  const shown = latest ?? null;

  return (
    <RequireRole allowed={can.seeGovernance}>
      <Topbar trail={[{ label: "Overview", href: "/" }, { label: "Fairness" }]} />
      <div className="page-head">
        <div>
          <h1>Fairness testing</h1>
          <p className="sub">Checks our own pipeline. It is not an independent bias audit.</p>
        </div>
        <div className="head-actions">
          <button className="btn btn-primary" disabled={busy} onClick={() => void run()}>
            {busy && <span className="spinner" />} Run counterfactual test
          </button>
        </div>
      </div>

      {shown && (
        <section className="panel panel-pad" style={{ marginBottom: 20 }}>
          <div className="panel-head">
            <h2>Latest result</h2>
            <span className={`tag ${shown.passed ? "tag-good" : "tag-bad"}`}>{shown.passed ? "Passed" : "Failed"}</span>
          </div>
          <ul className="plain-list">
            <li><strong className="num">{shown.summary.variants_tested}</strong> variants of one résumé tested (names, universities, pronouns)</li>
            <li><strong className="num">{shown.summary.variants_leaking}</strong> still showed identity after redaction</li>
            <li>Largest score difference between variants: <strong className="num">{shown.summary.max_score_difference}</strong> points</li>
          </ul>
          {shown.details && (
            <>
              <h3 style={{ marginTop: 16 }}>Known limits ({shown.summary.probe_leaks} of {shown.summary.probes_run} probes got through)</h3>
              <p className="muted">These cases are harder. They do not fail the test, but they show what redaction can miss.</p>
              <ul className="plain-list">
                {shown.details.probes.map((probe) => (
                  <li key={probe.case}>
                    <span className={`tag ${probe.leaked ? "tag-warn" : "tag-good"}`}>{probe.leaked ? "Not caught" : "Caught"}</span> {probe.case}
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      )}

      <section className="panel panel-pad" style={{ marginBottom: 20 }}>
        <div className="panel-head"><h2>Adverse impact (four-fifths rule)</h2></div>
        <p className="panel-sub">
          Enter real counts. A group whose selection rate is below 80% of the highest group is flagged. Small groups
          (under 30 applicants) are unreliable.
        </p>
        {groups.map((group, index) => (
          <div className="group-row" key={index}>
            <input className="input" aria-label="Group name" value={group.name} onChange={(e) => setGroups(groups.map((g, i) => (i === index ? { ...g, name: e.target.value } : g)))} />
            <input className="input" aria-label="Applicants" type="number" min={1} placeholder="Applicants" value={group.applicants} onChange={(e) => setGroups(groups.map((g, i) => (i === index ? { ...g, applicants: e.target.value } : g)))} />
            <input className="input" aria-label="Selected" type="number" min={0} placeholder="Selected" value={group.selected} onChange={(e) => setGroups(groups.map((g, i) => (i === index ? { ...g, selected: e.target.value } : g)))} />
          </div>
        ))}
        <div className="form-actions" style={{ justifyContent: "flex-start" }}>
          <button className="btn btn-ghost btn-sm" onClick={() => setGroups([...groups, { name: `Group ${groups.length + 1}`, applicants: "", selected: "" }])}>Add group</button>
          <button className="btn btn-primary btn-sm" onClick={() => void calculate()}>Calculate</button>
        </div>
        {impact && (
          <div className="data-table" style={{ marginTop: 14 }}>
            {impact.groups.map((group) => (
              <div className="data-row" key={group.name}>
                <div><strong>{group.name}</strong><span className="muted">{group.selected} of {group.applicants} selected</span></div>
                <div className="num">Rate {(group.rate * 100).toFixed(1)}%</div>
                <div className="num">Ratio {group.impact_ratio.toFixed(2)}</div>
                <div>
                  <span className={`tag ${group.flag ? "tag-bad" : "tag-good"}`}>{group.flag ? "Below 0.80" : "OK"}</span>
                  {group.small_sample && <span className="tag tag-warn" style={{ marginLeft: 6 }}>Small sample</span>}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="panel panel-pad">
        <div className="panel-head"><h2>History</h2></div>
        {error && <ErrorNotice message={error} onRetry={load} />}
        {!runs ? (
          !error && <LoadingBlock rows={2} />
        ) : runs.length === 0 ? (
          <p className="muted">No runs yet.</p>
        ) : (
          <div className="data-table">
            {runs.map((item) => (
              <div className="data-row" key={item.id}>
                <div className="num">{new Date(item.created_at).toLocaleString()}</div>
                <div>{item.by}</div>
                <div><span className={`tag ${item.passed ? "tag-good" : "tag-bad"}`}>{item.passed ? "Passed" : "Failed"}</span></div>
                <div className="muted">{item.summary.variants_tested} variants</div>
              </div>
            ))}
          </div>
        )}
      </section>
    </RequireRole>
  );
}
