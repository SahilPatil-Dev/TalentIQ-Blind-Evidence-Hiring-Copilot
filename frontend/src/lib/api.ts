/**
 * api.ts — the ONLY place the website talks to the Django backend.
 *
 * Every page calls `api.something()` instead of using fetch() directly, so if
 * the backend address or error handling ever changes, you fix it here once.
 */

// ---------- Types: the shape of the JSON the backend sends back ----------

export type Status = "PROCESSING" | "NEEDS_REVIEW" | "SHORTLISTED" | "REJECTED";

/** One scoring rule of a role, e.g. "Python backend", 40%, keywords [...]. */
export interface Criterion {
  name: string;
  weight: number;
  keywords: string[];
}

/** The proof (or lack of it) found in a résumé for one criterion. */
export interface Evidence {
  criterion: string;
  weight: number;
  status: "verified" | "partial" | "missing";
  quote: string; // exact sentence copied from the résumé ("" if missing)
}

/** One evaluated candidate. Note: there is NO name here (blind review). */
export interface Candidate {
  id: number;
  job: number;
  candidate_label: string; // e.g. "Candidate 0007"
  evidence_matrix: Evidence[];
  final_score: number; // 0–100
  interview_questions: string[];
  status: Status;
  workflow_trace: string[]; // steps the AI flow went through
  created_at: string;
  decided_at: string | null;
}

/** A candidate's detail page. `identity` only exists after shortlisting. */
export type CandidateDetail = Candidate & { identity?: Record<string, string> };

/** A position you are hiring for. */
export interface Role {
  id: number;
  title: string;
  department: string;
  rubric_markdown: string;
  rubric_criteria: Criterion[];
  application_count: number;
  needs_review_count?: number;
  created_at: string;
  applications?: Candidate[]; // only included by GET /jobs/<id>/
}

// ---------- Talking to the server ----------

// Set NEXT_PUBLIC_API_URL to your Render address when deploying (see README).
const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Small wrapper around fetch():
 *  - adds the API address
 *  - turns error responses into readable Error messages
 *  - for READ requests, waits and retries while a free Render server wakes up
 *    (it sleeps after 15 idle minutes and takes up to ~1 minute to start).
 */
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const isRead = !init?.method || init.method === "GET";
  const maxTries = isRead ? 8 : 1;
  let response: Response | null = null;

  for (let attempt = 1; attempt <= maxTries; attempt++) {
    try {
      response = await fetch(`${API_URL}/api${path}`, { ...init, cache: "no-store" });
      // 502/503/504 = the server is still waking up. Wait, then try again.
      const stillWaking = [502, 503, 504].includes(response.status);
      if (isRead && stillWaking && attempt < maxTries) {
        await sleep(6000);
        continue;
      }
      break;
    } catch {
      // Network error (server asleep, offline, wrong URL...)
      if (attempt === maxTries) {
        throw new Error(
          "Can't reach the TalentIQ API. If it's running on a free host it may still be waking up — wait a moment and try again."
        );
      }
      await sleep(6000);
    }
  }
  if (!response) throw new Error("No response from the TalentIQ API.");

  if (!response.ok) {
    // The backend sends {"detail": "..."} or {"field": ["error", ...]}.
    const body = await response.json().catch(() => null);
    const detail =
      body?.detail ??
      Object.entries(body ?? {})
        .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(", ") : value}`)
        .join("; ");
    throw new Error(detail || `Request failed (${response.status}).`);
  }
  return response.json() as Promise<T>;
}

/** One function per backend endpoint. */
export const api = {
  /** All roles (for the dashboard). */
  getRoles: () => request<Role[]>("/jobs/"),

  /** One role plus its candidates, already ranked by score. */
  getRole: (id: string) => request<Role>(`/jobs/${id}/`),

  /** Create a role with its scoring rubric. */
  createRole: (
    data: Pick<Role, "title" | "department" | "rubric_markdown" | "rubric_criteria">
  ) =>
    request<Role>("/jobs/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),

  /** One candidate's evidence review. */
  getApplication: (id: string) => request<CandidateDetail>(`/applications/${id}/`),

  /** Upload a résumé file. The backend redacts + evaluates it before answering. */
  uploadResume: (jobId: string, file: File) => {
    const form = new FormData();
    form.append("resume", file);
    return request<Candidate>(`/jobs/${jobId}/applications/`, { method: "POST", body: form });
  },

  /** The human decision: shortlist (reveals identity) or reject. */
  decide: (id: number, decision: "shortlist" | "reject") =>
    request<Candidate>(`/applications/${id}/decision/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision }),
    }),
};
