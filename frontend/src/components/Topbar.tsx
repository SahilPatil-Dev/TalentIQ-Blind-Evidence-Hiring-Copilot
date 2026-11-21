/**
 * Topbar.tsx — breadcrumbs on the left ("Overview > Role > Candidate") and the
 * "Private workspace" badge on the right. Each page passes its own `trail`.
 */
import Link from "next/link";
import { Icon } from "./Icon";
import { Brand } from "./Sidebar";

export interface Crumb {
  label: string;
  href?: string; // no href = the current page
}

export function Topbar({ trail }: { trail: Crumb[] }) {
  return (
    <header className="topbar">
      <div className="topbar-brand">
        <Brand />
      </div>
      <nav className="crumbs" aria-label="Breadcrumb">
        {trail.map((crumb, index) => (
          <span key={index} className="crumb">
            {index > 0 && <Icon name="chevronRight" size={14} />}
            {crumb.href ? <Link href={crumb.href}>{crumb.label}</Link> : <span className="current">{crumb.label}</span>}
          </span>
        ))}
      </nav>
      <span className="private">
        <i className="live-dot" /> Private workspace
      </span>
    </header>
  );
}
