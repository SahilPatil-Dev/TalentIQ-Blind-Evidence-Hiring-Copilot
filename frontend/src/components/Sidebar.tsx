"use client";
/**
 * Sidebar.tsx — the dark navigation rail on desktop, and a bottom tab bar on
 * phones. It lives in the layout, so it stays in place while pages change.
 */
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon, type IconName } from "./Icon";

/** Logo: a tiny résumé with one line highlighted and one line blacked out. */
export function Brand() {
  return (
    <Link className="brand" href="/" aria-label="TalentIQ home">
      <svg className="brand-mark" viewBox="0 0 32 32" aria-hidden="true">
        <rect width="32" height="32" rx="9" fill="#2f4bff" />
        <rect x="7" y="8" width="11" height="3.2" rx="1.6" fill="#fff" />
        <rect x="7" y="14.4" width="18" height="3.2" rx="1.6" fill="#ffe27a" />
        <rect x="7" y="20.8" width="13" height="3.2" rx="1.6" fill="#0e1726" />
      </svg>
      <span>
        talent<b>iq</b>
      </span>
    </Link>
  );
}

const LINKS: { href: string; label: string; icon: IconName }[] = [
  { href: "/", label: "Overview", icon: "grid" },
  { href: "/jobs/new", label: "New role", icon: "plus" },
];

export function Sidebar() {
  const pathname = usePathname();
  // "Overview" also stays highlighted on role and candidate pages (they belong to it).
  const isActive = (href: string) => (href === "/" ? pathname !== "/jobs/new" : pathname === href);

  return (
    <>
      <aside className="rail">
        <Brand />
        <nav className="nav" aria-label="Main">
          {LINKS.map((link) => (
            <Link key={link.href} href={link.href} className={`nav-link ${isActive(link.href) ? "active" : ""}`}>
              <Icon name={link.icon} /> {link.label}
            </Link>
          ))}
        </nav>

        {/* A little picture of what blind review does, plus the reminder. */}
        <div className="rail-note">
          <div className="lines" aria-hidden="true">
            <span className="line" style={{ width: "86%" }} />
            <span className="line sealed" style={{ width: "52%" }} />
            <span className="line" style={{ width: "72%" }} />
            <span className="line hit" style={{ width: "64%" }} />
          </div>
          <strong>Blind review is on</strong>
          <p>Names stay sealed until you shortlist a candidate.</p>
        </div>
      </aside>

      <nav className="tabbar" aria-label="Main">
        {LINKS.map((link) => (
          <Link key={link.href} href={link.href} className={isActive(link.href) ? "active" : ""}>
            <Icon name={link.icon} size={20} /> {link.label}
          </Link>
        ))}
      </nav>
    </>
  );
}
