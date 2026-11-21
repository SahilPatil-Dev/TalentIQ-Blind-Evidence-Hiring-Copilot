/**
 * PageState.tsx — the three "not the normal view" states every page needs:
 *   <LoadingBlock>  while data is loading (grey shimmering placeholders)
 *   <ErrorNotice>   when something failed, with a Try again button
 *   <EmptyState>    when there is nothing to show yet
 */
import type { ReactNode } from "react";
import { Icon } from "./Icon";

/** Shimmering placeholder rows. After ~5s it explains the free-server delay. */
export function LoadingBlock({ rows = 3 }: { rows?: number }) {
  return (
    <div aria-busy="true" aria-live="polite">
      <div className="panel panel-pad" style={{ display: "grid", gap: 14 }}>
        {Array.from({ length: rows }).map((_, index) => (
          <div key={index} className="skeleton" style={{ height: index === 0 ? 26 : 54, width: index === 0 ? "38%" : "100%" }} />
        ))}
      </div>
      <p className="cold-hint">
        Still loading… the free server goes to sleep when idle, so the first visit can take up to a minute.
      </p>
    </div>
  );
}

export function ErrorNotice({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="notice notice-error" role="alert">
      <Icon name="alert" size={20} />
      <div>
        <strong>Something went wrong</strong>
        <p>{message}</p>
      </div>
      {onRetry && (
        <button className="btn btn-ghost btn-sm" onClick={onRetry}>
          <Icon name="refresh" size={15} /> Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState({ icon, title, children }: { icon: "briefcase" | "users"; title: string; children: ReactNode }) {
  return (
    <div className="empty">
      <div className="empty-icon">
        <Icon name={icon} size={22} />
      </div>
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
