/**
 * format.ts — tiny helpers that turn raw data into display text / colours.
 * Keeping them here means every page shows things the same way.
 */
import type { Evidence, Status } from "./api";

export type Tone = "high" | "mid" | "low";

/** Colour band for a score: 75+ green, 50–74 amber, below that red. */
export function scoreTone(score: number): Tone {
  if (score >= 75) return "high";
  if (score >= 50) return "mid";
  return "low";
}

/** Human-friendly status names. */
export function statusLabel(status: Status): string {
  const labels: Record<Status, string> = {
    PROCESSING: "Processing",
    NEEDS_REVIEW: "Needs review",
    SHORTLISTED: "Shortlisted",
    REJECTED: "Archived",
  };
  return labels[status];
}

/** Points a criterion earned: verified = full weight, partial = half, missing = 0. */
export function earnedPoints(item: Evidence): number {
  const share = item.status === "verified" ? 1 : item.status === "partial" ? 0.5 : 0;
  return item.weight * share;
}

/** "Mar 4, 2026" in the visitor's own locale. */
export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/** Plural helper: plural(3, "role") -> "3 roles". */
export function plural(count: number, word: string): string {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}
