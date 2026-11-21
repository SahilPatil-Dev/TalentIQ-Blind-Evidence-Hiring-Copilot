/** StatusPill.tsx — the coloured label showing where a candidate is in the process. */
import type { Status } from "@/lib/api";
import { statusLabel } from "@/lib/format";

export function StatusPill({ status }: { status: Status }) {
  return <span className={`pill pill-${status.toLowerCase()}`}>{statusLabel(status)}</span>;
}
