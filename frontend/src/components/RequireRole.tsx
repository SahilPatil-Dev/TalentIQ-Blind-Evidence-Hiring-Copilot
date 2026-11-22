"use client";
/**
 * RequireRole.tsx — wrap a page in this to show a friendly message instead of the page
 * when the signed-in role is not allowed to use it. (The backend refuses anyway.)
 */
import type { ReactNode } from "react";
import type { RoleName } from "@/lib/api";
import { useAuth } from "./AuthProvider";
import { Icon } from "./Icon";

export function RequireRole({ allowed, children }: { allowed: (role?: RoleName) => boolean; children: ReactNode }) {
  const { user } = useAuth();
  if (!allowed(user?.role)) {
    return (
      <div className="notice notice-error" role="alert" style={{ marginTop: 28 }}>
        <Icon name="lock" size={20} />
        <div>
          <strong>Your role can&apos;t open this page</strong>
          <p>Ask an administrator if you need access.</p>
        </div>
      </div>
    );
  }
  return <>{children}</>;
}
