"use client";
/**
 * Sidebar.tsx — the dark navigation rail on desktop, and a bottom tab bar on
 * phones. It lives in the layout, so it stays in place while pages change.
 */
import Link from "next/link";
import { usePathname } from "next/navigation";
import { can, ROLE_LABEL } from "@/lib/roles";
import type { RoleName } from "@/lib/api";
import { useAuth } from "./AuthProvider";
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

interface NavItem {
  href: string;
  label: string;
  icon: IconName;
  allowed: (role?: RoleName) => boolean;
}

// Which links each role sees. The backend enforces access; this only tidies the menu.
const LINKS: NavItem[] = [
  { href: "/", label: "Overview", icon: "grid", allowed: can.viewCandidates },
  { href: "/jobs/new", label: "New role", icon: "plus", allowed: can.manageHiring },
  { href: "/audit", label: "Audit log", icon: "list", allowed: can.seeGovernance },
  { href: "/fairness", label: "Fairness", icon: "scale", allowed: can.seeGovernance },
  { href: "/compliance", label: "Compliance", icon: "clipboard", allowed: can.seeGovernance },
  { href: "/retention", label: "Retention", icon: "clock", allowed: can.seeGovernance },
  { href: "/keys", label: "Keys", icon: "key", allowed: can.admin },
  { href: "/users", label: "Users", icon: "users", allowed: can.admin },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, signOut } = useAuth();
  const links = LINKS.filter((link) => link.allowed(user?.role));
  // "Overview" also stays highlighted on role and candidate pages (they belong to it).
  const inOverview = pathname === "/" || (pathname.startsWith("/jobs/") && pathname !== "/jobs/new") || pathname.startsWith("/applications/");
  const isActive = (href: string) => (href === "/" ? inOverview : pathname === href);

  return (
    <>
      <aside className="rail">
        <Brand />
        <nav className="nav" aria-label="Main">
          {links.map((link) => (
            <Link key={link.href} href={link.href} className={`nav-link ${isActive(link.href) ? "active" : ""}`}>
              <Icon name={link.icon} /> {link.label}
            </Link>
          ))}
        </nav>

        {/* A little picture of what blind review does, plus the reminder. */}
        <div className="rail-user">
          <div>
            <strong>{user?.name}</strong>
            <span>{user ? ROLE_LABEL[user.role] : ""}</span>
          </div>
          <button className="icon-btn" aria-label="Sign out" onClick={() => void signOut()}>
            <Icon name="logout" size={17} />
          </button>
        </div>

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

      <nav className="tabbar" aria-label="Main" style={{ gridTemplateColumns: `repeat(${links.length + 1}, 1fr)` }}>
        {links.map((link) => (
          <Link key={link.href} href={link.href} className={isActive(link.href) ? "active" : ""}>
            <Icon name={link.icon} size={20} /> <span className="tab-label">{link.label}</span>
          </Link>
        ))}
        <a href="#signout" onClick={(event) => { event.preventDefault(); void signOut(); }}>
          <Icon name="logout" size={20} /> <span className="tab-label">Sign out</span>
        </a>
      </nav>
    </>
  );
}
