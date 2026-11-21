"use client";
/**
 * applications/[id]/page.tsx ("/applications/7") — one candidate's review.
 *
 * Left: the evidence matrix (the quote that earned each point) and the
 * evaluation trace. Right: the identity card and the interview questions.
 * Flow: load the candidate (api.getApplication). Clicking "Shortlist" calls
 * api.decide(); we reload, and now the backend includes the real identity, so
 * the redaction bars slide away.
 */
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Icon } from "@/components/Icon";
import { IdentityCard } from "@/components/IdentityCard";
import { ErrorNotice, LoadingBlock } from "@/components/PageState";
import { ScoreRing } from "@/components/ScoreRing";
import { StatusPill } from "@/components/StatusPill";
import { useToast } from "@/components/Toast";
import { Topbar } from "@/components/Topbar";
import { api, type CandidateDetail } from "@/lib/api";
import { earnedPoints } from "@/lib/format";

export default function ApplicationPage() {
  const params = useParams<{ id: string }>();
  const toast = useToast();
  const [application, setApplication] = useState<CandidateDetail | null>(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [copied, setCopied] = useState<number | null>(null); // which question was just copied

  const load = useCallback(async () => {
    try {
      setApplication(await api.getApplication(params.id));
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load this candidate.");
    }
  }, [params.id]);

  useEffect(() => {
    void load();
  }, [load]);

  // Record the human decision, then reload to get the updated candidate.
  async function decide(decision: "shortlist" | "reject") {
    if (!application) return;
    setSaving(true);
    try {
      await api.decide(application.id, decision);
      await load();
      toast("success", decision === "shortlist" ? "Shortlisted. Identity revealed." : "Candidate archived.");
    } catch (reason) {
      toast("error", reason instanceof Error ? reason.message : "Could not record the decision.");
    } finally {
      setSaving(false);
    }
  }

  async function copyQuestion(question: string, index: number) {
    await navigator.clipboard.writeText(question);
    setCopied(index);
    window.setTimeout(() => setCopied(null), 1600);
  }

  return (
    <>
      <Topbar
        trail={[
          { label: "Overview", href: "/" },
          { label: "Role", href: application ? `/jobs/${application.job}` : "/" },
          { label: application?.candidate_label ?? "Candidate" },
        ]}
      />
      {error && <ErrorNotice message={error} onRetry={application ? undefined : load} />}

      {!application ? (
        !error && <LoadingBlock rows={4} />
      ) : (
        <>
          <Link href={`/jobs/${application.job}`} className="back">
            <Icon name="arrowLeft" size={15} /> Back to candidates
          </Link>
          <div className="page-head">
            <div>
              <h1>{application.candidate_label}</h1>
              <div className="meta">
                <StatusPill status={application.status} />
                <span><Icon name="eyeOff" size={15} /> Reviewed without name or contact details</span>
              </div>
            </div>
            <div className="head-score"><ScoreRing value={application.final_score} /></div>
          </div>

          <div className="workbench">
            <div className="stack">
              {/* Evidence matrix: the heart of the product */}
              <section className="panel">
                <div className="panel-pad" style={{ paddingBottom: 0 }}>
                  <div className="panel-head"><h2>Evidence</h2></div>
                  <p className="panel-sub">Each point comes from a sentence in the résumé. No quote, no points.</p>
                </div>
                {application.evidence_matrix.map((item, index) => {
                  const earned = earnedPoints(item);
                  return (
                    <article className="ev-item" key={item.criterion}>
                      <div className="ev-top">
                        <span className="ev-name">{item.criterion}</span>
                        <span className="ev-weight num">{item.weight}% of the score</span>
                        <span className={`ev-status ${item.status}`}>
                          {item.status === "verified" && <><Icon name="check" size={15} /> Verified</>}
                          {item.status === "partial" && <><Icon name="clock" size={15} /> Partial</>}
                          {item.status === "missing" && <>Missing</>}
                        </span>
                      </div>
                      {item.quote ? (
                        <blockquote className={`quote ${item.status}`}>
                          <span className="mark" style={{ "--d": `${0.3 + index * 0.25}s` } as React.CSSProperties}>{item.quote}</span>
                        </blockquote>
                      ) : (
                        <p className="no-quote">No supporting sentence found in this résumé.</p>
                      )}
                      <div className="points">
                        <div className="meter"><i style={{ width: `${item.weight ? (earned / item.weight) * 100 : 0}%` }} /></div>
                        <span><b className="num">+{earned}</b> of {item.weight} points</span>
                      </div>
                    </article>
                  );
                })}
              </section>

              {/* What the evaluation flow did */}
              <section className="panel">
                <div className="panel-pad" style={{ paddingBottom: 8 }}>
                  <div className="panel-head" style={{ marginBottom: 0 }}><h2>How this score was made</h2></div>
                </div>
                <ol className="trace">
                  {application.workflow_trace.map((step, index) => (
                    <li key={`${step}-${index}`} style={{ "--i": index } as React.CSSProperties}>
                      <span className="tick"><Icon name="check" size={13} /></span>
                      {step}
                    </li>
                  ))}
                </ol>
              </section>
            </div>

            <div className="stack">
              <IdentityCard
                identity={application.identity}
                status={application.status}
                busy={saving}
                onShortlist={() => void decide("shortlist")}
                onReject={() => void decide("reject")}
              />

              <section className="panel panel-pad">
                <div className="panel-head"><h2>Interview questions</h2></div>
                <p className="panel-sub">Aimed at the gaps. Use them to verify experience in conversation.</p>
                {application.interview_questions.map((question, index) => (
                  <div className="q" key={question}>
                    <span className="q-n num">{index + 1}</span>
                    <p>{question}</p>
                    <button className={`copy ${copied === index ? "copied" : ""}`} aria-label={`Copy question ${index + 1}`} onClick={() => void copyQuestion(question, index)}>
                      <Icon name={copied === index ? "check" : "copy"} size={16} />
                    </button>
                  </div>
                ))}
              </section>
            </div>
          </div>
        </>
      )}
    </>
  );
}
