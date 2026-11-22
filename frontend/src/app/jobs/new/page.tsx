"use client";
/**
 * jobs/new/page.tsx ("/jobs/new") — the form that creates a role.
 *
 * Flow: you fill in the title and the scoring criteria. The coloured bar and the
 * total update live. When the weights add up to 100 the button turns on and
 * api.createRole() saves it, then we jump to the new role's page.
 */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { RequireRole } from "@/components/RequireRole";
import { Icon } from "@/components/Icon";
import { RubricBar } from "@/components/RubricBar";
import { Topbar } from "@/components/Topbar";
import { api } from "@/lib/api";
import { can } from "@/lib/roles";

// While typing, keywords are plain text ("Python, Django"). We split them into
// a list only when saving.
interface CriterionDraft {
  name: string;
  weight: number;
  keywordsText: string;
}

const STARTER: CriterionDraft[] = [
  { name: "Python backend", weight: 40, keywordsText: "Python, Django, REST API" },
  { name: "AI agents", weight: 35, keywordsText: "LangGraph, RAG, AI agents" },
  { name: "System design", weight: 25, keywordsText: "PostgreSQL, Redis, Docker" },
];

export default function NewRolePage() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [department, setDepartment] = useState("Engineering");
  const [rubric, setRubric] = useState("");
  const [criteria, setCriteria] = useState(STARTER);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  // Change one field of one criterion row.
  function update(index: number, field: keyof CriterionDraft, value: string) {
    setCriteria((rows) =>
      rows.map((row, i) => (i === index ? { ...row, [field]: field === "weight" ? Number(value) : value } : row))
    );
  }
  const addRow = () => setCriteria((rows) => [...rows, { name: "", weight: Math.max(0, 100 - total), keywordsText: "" }]);
  const removeRow = (index: number) => setCriteria((rows) => rows.filter((_, i) => i !== index));

  const total = criteria.reduce((sum, row) => sum + (Number(row.weight) || 0), 0);
  const isValid = total === 100;

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const role = await api.createRole({
        title,
        department,
        rubric_markdown: rubric,
        rubric_criteria: criteria.map((row) => ({
          name: row.name,
          weight: row.weight,
          keywords: row.keywordsText.split(",").map((word) => word.trim()).filter(Boolean),
        })),
      });
      router.push(`/jobs/${role.id}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not create the role.");
      setSaving(false);
    }
  }

  // The hint next to the total, e.g. "Add 15 more".
  const hint = isValid ? "Ready" : total < 100 ? `Add ${100 - total} more` : `Remove ${total - 100}`;

  return (
    <RequireRole allowed={can.manageHiring}>
      <Topbar trail={[{ label: "Overview", href: "/" }, { label: "New role" }]} />
      <div className="page-head">
        <div>
          <h1>Create a hiring pipeline</h1>
          <p className="sub">Say what good looks like. Scores come only from quoted evidence.</p>
        </div>
      </div>

      <form className="form-grid" onSubmit={submit}>
        <div>
          <section className="panel panel-pad" style={{ marginBottom: 20 }}>
            <div className="panel-head"><h2>Role details</h2></div>
            <label className="field">
              <span>Role title</span>
              <input className="input" required value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Junior AI & Backend Engineer" />
            </label>
            <label className="field">
              <span>Department</span>
              <input className="input" value={department} onChange={(e) => setDepartment(e.target.value)} placeholder="Engineering" />
            </label>
            <label className="field" style={{ marginBottom: 0 }}>
              <span>What a strong candidate looks like <small>(optional)</small></span>
              <textarea className="input" rows={3} value={rubric} onChange={(e) => setRubric(e.target.value)} placeholder="Describe the requirements and what strong evidence looks like…" />
            </label>
          </section>

          <section className="panel panel-pad">
            <div className="panel-head"><h2>Scoring criteria</h2></div>
            <p className="panel-sub">Weights must add up to 100. Keywords help the offline matcher; the AI reads the whole résumé.</p>

            <RubricBar criteria={criteria.map((row) => ({ name: row.name, weight: row.weight }))} />

            <div className="total-line">
              <span>Total weight</span>
              <span className={`total-pill num ${isValid ? "total-ok" : "total-bad"}`}>{total}% · {hint}</span>
            </div>

            <div className="crit-head"><span>Criterion</span><span>Keywords (comma-separated)</span><span>Weight</span><span /></div>
            {criteria.map((row, index) => (
              <div className="crit" key={index}>
                <input className="input" aria-label="Criterion name" required value={row.name} onChange={(e) => update(index, "name", e.target.value)} placeholder="e.g. Cloud" />
                <input className="input" aria-label="Keywords" value={row.keywordsText} onChange={(e) => update(index, "keywordsText", e.target.value)} placeholder="AWS, Terraform" />
                <div className="weight-field">
                  <input className="input" aria-label="Weight" type="number" min={1} max={100} required value={row.weight} onChange={(e) => update(index, "weight", e.target.value)} />
                  <span>%</span>
                </div>
                <button type="button" className="icon-btn" aria-label="Remove criterion" disabled={criteria.length === 1} onClick={() => removeRow(index)}>
                  <Icon name="trash" size={17} />
                </button>
              </div>
            ))}
            <button type="button" className="btn btn-ghost btn-sm" onClick={addRow}>
              <Icon name="plus" size={15} /> Add criterion
            </button>

            {error && (
              <div className="notice notice-error" role="alert" style={{ marginTop: 18 }}>
                <Icon name="alert" size={20} />
                <div><strong>Couldn&apos;t create the role</strong><p>{error}</p></div>
              </div>
            )}

            <div className="form-actions" style={{ marginTop: 22 }}>
              <Link href="/" className="btn btn-ghost">Cancel</Link>
              <button className="btn btn-primary" type="submit" disabled={saving || !isValid}>
                {saving && <span className="spinner" />} {saving ? "Creating…" : "Create pipeline"}
              </button>
            </div>
          </section>
        </div>

        <aside className="guide">
          <h3>How scoring works</h3>
          <ul>
            <li><Icon name="eyeOff" size={18} /><div><strong>Identity is hidden first</strong>The AI never sees names, emails or universities.</div></li>
            <li><Icon name="file" size={18} /><div><strong>Every point has a quote</strong>Verified earns full weight, partial earns half, missing earns none.</div></li>
            <li><Icon name="check" size={18} /><div><strong>Python does the maths</strong>The same résumé always gets the same score.</div></li>
            <li><Icon name="users" size={18} /><div><strong>You decide</strong>Nothing is shortlisted or rejected automatically.</div></li>
          </ul>
        </aside>
      </form>
    </RequireRole>
  );
}
