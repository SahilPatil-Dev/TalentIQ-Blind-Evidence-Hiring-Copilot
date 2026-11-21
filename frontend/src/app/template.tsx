/**
 * template.tsx — unlike layout.tsx, Next.js re-creates this on every page
 * change. That makes the soft fade-in (see `.page` in globals.css) replay
 * each time you navigate.
 */
export default function Template({ children }: { children: React.ReactNode }) {
  return <div className="page">{children}</div>;
}
