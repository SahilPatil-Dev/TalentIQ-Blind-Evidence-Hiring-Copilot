"use client";
/**
 * DashboardView.tsx — the signed-in home page ("/"): the dashboard.
 *
 * Flow: when the page opens we ask the API for all roles (api.getRoles), then
 * show: the hero + animated demo, a stats strip, a "how it works" strip, and
 * the list of hiring pipelines (roles). Click a role to open it.
 */
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { CountUp } from "@/components/CountUp";
import { Icon } from "@/components/Icon";
import { EmptyState, ErrorNotice, LoadingBlock } from "@/components/PageState";
import { RedactionDemo } from "@/components/RedactionDemo";
import { RubricBar } from "@/components/RubricBar";
import { Topbar } from "@/components/Topbar";
import { api, type Role } from "@/lib/api";
import { plural } from "@/lib/format";
import { can } from "@/lib/roles";

// The four steps a résumé goes through (shown in the "how it works" strip).
const STEPS = [
  { title: "Hide identity", text: "Name, email, phone, university and pronouns are removed and locked away." },
  { title: "Find evidence", text: "Codestral quotes the résumé sentence that proves each skill on your rubric." },
  { title: "Verify quotes", text: "Python checks every quote exists word for word. Invented claims earn nothing." },
  { title: "You decide", text: "Python adds up the score. You shortlist or archive with a reason; revealing identity is logged." },
];

export function DashboardView() {
  const { user } = useAuth();
  const [roles, setRoles] = useState<Role[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  // Load the roles from the backend.
  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setRoles(await api.getRoles());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load roles.");
    } finally {
      setLoading(false);
    }
  }, []);

  // Run it once when the page first appears.
  useEffect(() => {
    void load();
  }, [load]);

  // Numbers for the stats strip.
  const totalCandidates = roles.reduce((sum, role) => sum + role.application_count, 0);
  const awaiting = roles.reduce((sum, role) => sum + (role.needs_review_count ?? 0), 0);

  return (
    <>
      <Topbar trail={[{ label: "Overview" }]} />

      {/* Hero: headline on the left, animated sample résumé on the right */}
      <section className="panel hero">
        <div>
          <h1>Hire on evidence. Names come later.</h1>
          <p className="lead">
            TalentIQ hides who a candidate is, quotes the proof in their résumé, and scores it with plain maths. Every
            decision stays with you.
          </p>
          <div className="hero-actions">
            {can.manageHiring(user?.role) && (
              <Link href="/jobs/new" className="btn btn-primary">
                <Icon name="plus" size={17} /> Create a role
              </Link>
            )}
            {roles[0] && (
              <Link href={`/jobs/${roles[0].id}`} className="btn btn-ghost">
                Open the sample pipeline
              </Link>
            )}
          </div>
        </div>
        <RedactionDemo />
      </section>

      {/* Stats strip */}
      <section className="panel ledger" aria-label="Summary">
        <div>
          <div className="big"><CountUp value={roles.length} pad={2} /></div>
          <div className="label">Active roles</div>
        </div>
        <div>
          <div className="big"><CountUp value={totalCandidates} pad={2} /></div>
          <div className="label">Candidates evaluated</div>
        </div>
        <div>
          <div className="big"><CountUp value={awaiting} pad={2} /></div>
          <div className="label">Waiting for your decision</div>
        </div>
        <div>
          <div className="big"><i className="live-dot" /> On</div>
          <div className="label">Blind review</div>
        </div>
      </section>

      {/* How it works */}
      <div className="section-head">
        <div>
          <h2>How a résumé becomes a score</h2>
        </div>
      </div>
      <section className="panel flow">
        {STEPS.map((step, index) => (
          <div className="flow-step" key={step.title}>
            <span className="n">{index + 1}</span>
            <h3>{step.title}</h3>
            <p>{step.text}</p>
          </div>
        ))}
      </section>

      {/* Roles */}
      <div className="section-head">
        <div>
          <h2>Hiring pipelines</h2>
          <p>Each role has its own weighted rubric.</p>
        </div>
        <span className="count-tag">{plural(roles.length, "role")}</span>
      </div>

      {error && <ErrorNotice message={error} onRetry={load} />}
      {loading ? (
        <LoadingBlock />
      ) : roles.length > 0 ? (
        <section className="panel rows">
          {roles.map((role) => (
            <Link href={`/jobs/${role.id}`} className="role-row" key={role.id}>
              <div>
                <div className="role-title">{role.title}</div>
                <div className="role-dept">{role.department || "Engineering"}</div>
              </div>
              <div className="rubric">
                <RubricBar criteria={role.rubric_criteria} compact />
              </div>
              <div className="role-count">
                <strong className="num">{role.application_count}</strong>
                <span>{role.application_count === 1 ? "candidate" : "candidates"}</span>
                {!!role.needs_review_count && <div className="review">{role.needs_review_count} to review</div>}
              </div>
              <Icon name="chevronRight" className="chev" />
            </Link>
          ))}
        </section>
      ) : (
        !error && (
          <section className="panel">
            <EmptyState icon="briefcase" title="Create your first pipeline">
              Add a role and a weighted rubric, then upload résumés for an evidence-based review.
            </EmptyState>
          </section>
        )
      )}

      <p className="footer-note">
        <Icon name="shield" size={18} /> TalentIQ never makes a hiring decision. Every outcome needs your review.
      </p>
    </>
  );
}
