/**
 * Shell.tsx — the frame around every page: sidebar on the left, page on the right.
 * It is used once, in layout.tsx, so the sidebar doesn't reload between pages.
 */
import type { ReactNode } from "react";
import { Sidebar } from "./Sidebar";

export function Shell({ children }: { children: ReactNode }) {
  return (
    <div className="shell">
      <Sidebar />
      <main className="content">
        <div className="content-inner">{children}</div>
      </main>
    </div>
  );
}
