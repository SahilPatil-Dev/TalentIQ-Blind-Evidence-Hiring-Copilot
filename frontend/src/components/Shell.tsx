"use client";
/**
 * Shell.tsx — the frame around every page: sidebar on the left, page on the right.
 * Login and register pages use a plain centred layout instead, and visitors who are not
 * signed in see the full-width landing page at "/". Everything else waits until we know
 * who is signed in.
 */
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { PUBLIC_PATHS, useAuth } from "./AuthProvider";
import { Sidebar } from "./Sidebar";

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { user, loading } = useAuth();

  if (PUBLIC_PATHS.includes(pathname)) return <main className="auth-page">{children}</main>;
  // The landing page is the public home page: full width, no sidebar.
  if (pathname === "/" && !loading && !user) return <>{children}</>;
  if (loading || !user) return <main className="auth-page"><span className="spinner dark" aria-label="Loading" /></main>;

  return (
    <div className="shell">
      <Sidebar />
      <main className="content">
        <div className="content-inner">{children}</div>
      </main>
    </div>
  );
}
