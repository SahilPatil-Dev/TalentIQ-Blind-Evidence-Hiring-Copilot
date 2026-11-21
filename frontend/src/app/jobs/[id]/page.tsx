"use client";
/**
 * jobs/[id]/page.tsx ("/jobs/3") — one role and its ranked candidates.
 *
 * Flow: load the role (api.getRole). Dropping résumé files calls
 * api.uploadResume() for each file, one after another. The backend redacts and
 * evaluates each one, then we reload the list so the new candidate appears in
 * ranked position. Click a candidate to review their evidence.
 */
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Icon } from "@/components/Icon";
import { EmptyState, ErrorNotice, LoadingBlock } from "@/components/PageState";
import { RubricBar } from "@/components/RubricBar";
import { StatusPill } from "@/components/StatusPill";
import { useToast } from "@/components/Toast";
import { Topbar } from "@/components/Topbar";
import { UploadZone, type UploadProgress } from "@/components/UploadZone";
import { api, type Role, type Status } from "@/lib/api";
import { formatDate, scoreTone } from "@/lib/format";

const FILTERS: { label: string; value: Status | "ALL" }[] = [
  { label: "All", value: "ALL" },
  { label: "Needs review", value: "NEEDS_REVIEW" },
  { label: "Shortlisted", value: "SHORTLISTED" },
  { label: "Archived", value: "REJECTED" },
];

export default function RolePage() {
  const params = useParams<{ id: string }>();
  const toast = useToast();
  const [role, setRole] = useState<Role | null>(null);
  const [filter, setFilter] = useState<Status | "ALL">("ALL");
  const [error, setError] = useState("");
  const [progress, setProgress] = useState<UploadProgress | null>(null);

  // Load (or reload) the role and its candidates.
  const loadRole = useCallback(async () => {
    try {
      setRole(await api.getRole(params.id));
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load this role.");
    }
  }, [params.id]);

  useEffect(() => {
    void loadRole();
  }, [loadRole]);

  // Upload each chosen file in turn, showing progress and a toast per result.
  async function uploadFiles(files: File[]) {
    const failures: string[] = [];
    for (let index = 0; index < files.length; index++) {
      setProgress({ current: index + 1, total: files.length, name: files[index].name });
      try {
        const candidate = await api.uploadResume(params.id, files[index]);
        toast("success", `${candidate.candidate_label} scored ${candidate.final_score}/100`);
      } catch (reason) {
        failures.push(`${files[index].name}: ${reason instanceof Error ? reason.message : "failed"}`);
      }
    }
    setProgress(null);
    setError(failures.join(" • "));
    await loadRole();
  }

  const applications = role?.applications ?? [];
  const visible = applications.filter((c) => filter === "ALL" || c.status === filter);
  const countOf = (value: Status | "ALL") => (value === "ALL" ? applications.length : applications.filter((c) => c.status === value).length);

  return (
    <>
      <Topbar trail={[{ label: "Overview", href: "/" }, { label: role?.title ?? "Role" }]} />
      {error && <ErrorNotice message={error} onRetry={role ? undefined : loadRole} />}

      {!role ? (
        !error && <LoadingBlock rows={4} />
      ) : (
        <>
          <div className="page-head">
            <div>
              <h1>{role.title}</h1>
              <div className="meta">
                <span><Icon name="briefcase" size={15} /> {role.department || "Engineering"}</span>
                <span><Icon name="clock" size={15} /> Created {formatDate(role.created_at)}</span>
              </div>
            </div>
          </div>

          {/* The rubric as a weighted bar */}
          <section className="panel panel-pad">
            <div className="panel-head"><h2>What this role values</h2></div>
            <RubricBar criteria={role.rubric_criteria} />
            <div className="mini-stats">
              <div><strong className="num">{applications.length}</strong> applicants</div>
              <div><strong className="num">{countOf("NEEDS_REVIEW")}</strong> waiting for review</div>
              <div><strong className="num">{countOf("SHORTLISTED")}</strong> shortlisted</div>
            </div>
          </section>

          <div className="section-head"><div><h2>Add résumés</h2></div></div>
          <UploadZone onFiles={uploadFiles} progress={progress} />

          <div className="section-head">
            <div>
              <h2>Candidates</h2>
              <p>Ranked by score. Names stay sealed while you review.</p>
            </div>
          </div>

          <div className="tabs" role="tablist" aria-label="Filter candidates">
            {FILTERS.map((item) => (
              <button key={item.value} role="tab" className="tab" aria-selected={filter === item.value} onClick={() => setFilter(item.value)}>
                {item.label} <span className="count num">{countOf(item.value)}</span>
              </button>
            ))}
          </div>

          <section className="panel rows">
            {visible.length > 0 ? (
              <>
                <div className="table-head">
                  <span>Candidate</span><span>Evidence</span><span>Score</span><span>Status</span><span />
                </div>
                {visible.map((candidate) => {
                  const tone = scoreTone(candidate.final_score);
                  return (
                    <Link href={`/applications/${candidate.id}`} className="cand-row" key={candidate.id}>
                      <div className="cand-who">
                        <span className="seal"><Icon name="lock" size={17} /></span>
                        <div>
                          <strong>{candidate.candidate_label}</strong>
                          <small>Identity sealed</small>
                        </div>
                      </div>
                      {/* one little block per criterion: green verified, amber partial, grey missing */}
                      <div className="evstrip col-ev" aria-label="Evidence per criterion">
                        {candidate.evidence_matrix.map((item) => (
                          <i key={item.criterion} className={item.status} title={`${item.criterion}: ${item.status}`} />
                        ))}
                      </div>
                      <div className="score-cell">
                        <strong className={`num tone-${tone}`}>{candidate.final_score}</strong>
                        <div className="meter"><i className={`tone-${tone}`} style={{ width: `${candidate.final_score}%` }} /></div>
                      </div>
                      <StatusPill status={candidate.status} />
                      <Icon name="chevronRight" className="chev" />
                    </Link>
                  );
                })}
              </>
            ) : (
              <EmptyState icon="users" title={applications.length ? "No candidates in this view" : "No candidates yet"}>
                {applications.length ? "Try another filter." : "Upload a PDF, TXT or Markdown résumé above to run a private evidence review."}
              </EmptyState>
            )}
          </section>
        </>
      )}
    </>
  );
}
