"use client";
/**
 * page.tsx (the home page, "/") — visitors who are not signed in see the landing page,
 * signed-in people see their dashboard.
 */
import { useAuth } from "@/components/AuthProvider";
import { DashboardView } from "@/components/DashboardView";
import { Landing } from "@/components/Landing";

export default function Home() {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="auth-page">
        <span className="spinner dark" aria-label="Loading" />
      </div>
    );
  }
  return user ? <DashboardView /> : <Landing />;
}
