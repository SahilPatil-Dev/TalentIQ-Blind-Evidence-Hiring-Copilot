/**
 * roles.ts — what each role may do. The BACKEND enforces all of this; the website only
 * uses it to hide buttons and pages a person could not use anyway.
 */
import type { RoleName } from "./api";

export const ROLE_LABEL: Record<RoleName, string> = {
  admin: "Administrator",
  recruiter: "Recruiter",
  reviewer: "Reviewer",
  auditor: "Auditor",
};

export const ROLE_HELP: Record<RoleName, string> = {
  admin: "Everything: users, keys, retention, deletion.",
  recruiter: "Create roles, upload résumés, decide, reveal identity.",
  reviewer: "Read-only blind review of candidates.",
  auditor: "Audit log, fairness tests and compliance. No candidate data.",
};

export const can = {
  viewCandidates: (role?: RoleName) => role === "admin" || role === "recruiter" || role === "reviewer",
  manageHiring: (role?: RoleName) => role === "admin" || role === "recruiter",
  seeGovernance: (role?: RoleName) => role === "admin" || role === "auditor",
  admin: (role?: RoleName) => role === "admin",
};
