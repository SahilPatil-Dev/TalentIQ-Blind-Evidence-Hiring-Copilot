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
  decision_reason: string;
  legal_hold: boolean;
}

/** One past identity reveal: who, why, when. */
export interface RevealEntry {
  by: string;
  reason: string;
  at: string;
}

/** A candidate's detail page. The identity is NOT included: ask for it with api.reveal(). */
export type CandidateDetail = Candidate & { reveal_history: RevealEntry[] };

export type RoleName = "admin" | "recruiter" | "reviewer" | "auditor";

export interface User {
  id: number;
  email: string;
  name: string;
  role: RoleName;
  is_approved: boolean;
  is_active: boolean;
  date_joined: string;
}

export interface AuditEntry {
  id: number;
  at: string;
  actor: string;
  action: string;
  target_type: string;
  target_id: string;
  detail: Record<string, unknown>;
  ip: string;
  hash: string;
}

export interface RetentionPolicy {
  rejected_days: number;
  undecided_days: number;
  shortlisted_days: number;
  last_run_at: string | null;
  last_run_deleted: number;
  due_now: number;
  on_legal_hold: number;
}

export interface KeyReport {
  keys: { version: number; status: "active" | "retired"; created_at: string; retired_at: string | null; records: number }[];
  legacy_records: number;
  master_key_configured: boolean;
}

export interface FairnessRun {
  id: number;
  created_at: string;
  by: string;
  passed: boolean;
  summary: {
    variants_tested: number;
    variants_leaking: number;
    max_score_difference: number;
    mean_score_by_name_set: Record<string, number>;
    probe_leaks: number;
    probes_run: number;
  };
  details?: { leaking_examples: unknown[]; probes: { case: string; leaked: boolean }[] };
}

export interface ImpactResult {
  groups: { name: string; applicants: number; selected: number; rate: number; impact_ratio: number; flag: boolean; small_sample: boolean }[];
  any_flag: boolean;
}

export interface ComplianceCheck {
  id: string;
  area: string;
  title: string;
  status: "pass" | "warn" | "fail" | "manual";
  detail: string;
  reference: string;
}

export interface ComplianceReport {
  generated_at: string;
  counts: Record<"pass" | "warn" | "fail" | "manual", number>;
  checks: ComplianceCheck[];
  disclaimer: string;
}

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

// ---------- Login session (token kept in this browser tab's storage) ----------
// sessionStorage clears when the tab closes. Tokens also expire on the server.
const TOKEN_KEY = "talentiq_token";
export const SIGNED_OUT_EVENT = "talentiq:signed-out";

export const tokenStore = {
  get(): string | null {
    try {
      return sessionStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set(value: string) {
    try {
      sessionStorage.setItem(TOKEN_KEY, value);
    } catch {
      /* storage blocked: the user will simply have to sign in again */
    }
  },
  clear() {
    try {
      sessionStorage.removeItem(TOKEN_KEY);
    } catch {
      /* ignore */
    }
  },
};

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

  const headers = new Headers(init?.headers);
  const token = tokenStore.get();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  for (let attempt = 1; attempt <= maxTries; attempt++) {
    try {
      response = await fetch(`${API_URL}/api${path}`, { ...init, headers, cache: "no-store" });
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

  // The session ended (expired, logged out elsewhere): send the user to the sign-in page.
  if (response.status === 401 && token && !path.startsWith("/auth/login")) {
    tokenStore.clear();
    window.dispatchEvent(new Event(SIGNED_OUT_EVENT));
  }

  if (response.status === 204) return undefined as T;

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

  /** The human decision. A written reason is required (kept in the audit log). */
  decide: (id: number, decision: "shortlist" | "reject", reason: string) =>
    request<Candidate>(`/applications/${id}/decision/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision, reason }),
    }),

  /** Audited identity reveal (shortlisted candidates only). */
  reveal: (id: number, reason: string) =>
    request<{ identity: Record<string, string> }>(`/applications/${id}/reveal/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason }),
    }),

  // ----- accounts -----
  register: (data: { name: string; email: string; password: string }) =>
    request<{ status: "active" | "pending"; message: string }>("/auth/register/", json("POST", data)),
  login: (email: string, password: string) =>
    request<{ token: string; expires_at: string; user: User }>("/auth/login/", json("POST", { email, password })),
  logout: () => request<void>("/auth/logout/", { method: "POST" }),
  me: () => request<User>("/auth/me/"),
  changePassword: (current_password: string, new_password: string) =>
    request<{ detail: string }>("/auth/password/", json("POST", { current_password, new_password })),
  getUsers: () => request<User[]>("/users/"),
  updateUser: (id: number, changes: Partial<Pick<User, "role" | "is_approved" | "is_active">>) =>
    request<User>(`/users/${id}/`, json("PATCH", changes)),

  // ----- governance -----
  getAudit: (action = "") => request<AuditEntry[]>(`/audit/${action ? `?action=${encodeURIComponent(action)}` : ""}`),
  verifyAudit: () => request<{ valid: boolean; checked: number; first_bad_id: number | null }>("/audit/verify/"),
  getRetention: () => request<RetentionPolicy>("/retention/"),
  saveRetention: (data: Pick<RetentionPolicy, "rejected_days" | "undecided_days" | "shortlisted_days">) =>
    request<RetentionPolicy>("/retention/", json("PUT", data)),
  runRetention: (dry_run: boolean) =>
    request<{ dry_run: boolean; deleted: number; due: number }>("/retention/run/", json("POST", { dry_run })),
  getKeys: () => request<KeyReport>("/keys/"),
  rotateKey: () => request<KeyReport>("/keys/rotate/", { method: "POST" }),
  reencrypt: () => request<KeyReport & { records_reencrypted: number }>("/keys/reencrypt/", { method: "POST" }),
  getFairnessRuns: () => request<FairnessRun[]>("/fairness/runs/"),
  runFairness: () => request<FairnessRun>("/fairness/runs/", { method: "POST" }),
  adverseImpact: (groups: { name: string; applicants: number; selected: number }[]) =>
    request<ImpactResult>("/fairness/adverse-impact/", json("POST", { groups })),
  getCompliance: () => request<ComplianceReport>("/compliance/"),

  /** Download the audit log as CSV (needs the token, so it can't be a plain link). */
  async downloadAuditCsv() {
    const response = await fetch(`${API_URL}/api/audit/?format=csv`, {
      headers: { Authorization: `Bearer ${tokenStore.get() ?? ""}` },
    });
    if (!response.ok) throw new Error("Could not export the audit log.");
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement("a");
    link.href = url;
    link.download = "talentiq-audit-log.csv";
    link.click();
    URL.revokeObjectURL(url);
  },
};

/** Small helper: JSON request options. */
function json(method: string, body: unknown): RequestInit {
  return { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}
