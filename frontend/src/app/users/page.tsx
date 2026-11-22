"use client";
/** users/page.tsx ("/users") — administrators approve accounts and choose roles. */
import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { ErrorNotice, LoadingBlock } from "@/components/PageState";
import { RequireRole } from "@/components/RequireRole";
import { useToast } from "@/components/Toast";
import { Topbar } from "@/components/Topbar";
import { api, type RoleName, type User } from "@/lib/api";
import { can, ROLE_HELP, ROLE_LABEL } from "@/lib/roles";

const ROLES: RoleName[] = ["admin", "recruiter", "reviewer", "auditor"];

export default function UsersPage() {
  const toast = useToast();
  const { user: me } = useAuth();
  const [users, setUsers] = useState<User[] | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setUsers(await api.getUsers());
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load users.");
    }
  }, []);

  useEffect(() => {
    if (can.admin(me?.role)) void load();
  }, [load, me]);

  async function change(id: number, changes: Partial<Pick<User, "role" | "is_approved" | "is_active">>) {
    try {
      await api.updateUser(id, changes);
      await load();
      toast("success", "User updated.");
    } catch (reason) {
      toast("error", reason instanceof Error ? reason.message : "Could not update the user.");
    }
  }

  return (
    <RequireRole allowed={can.admin}>
      <Topbar trail={[{ label: "Overview", href: "/" }, { label: "Users" }]} />
      <div className="page-head">
        <div>
          <h1>Users and roles</h1>
          <p className="sub">New accounts cannot sign in until you approve them.</p>
        </div>
      </div>
      {error && <ErrorNotice message={error} onRetry={load} />}
      {!users ? (
        !error && <LoadingBlock rows={4} />
      ) : (
        <section className="panel">
          <div className="data-table">
            {users.map((row) => (
              <div className="data-row" key={row.id}>
                <div>
                  <strong>{row.name}</strong>
                  <span className="muted">{row.email}</span>
                </div>
                <div>
                  {row.is_approved ? (
                    <span className={`tag ${row.is_active ? "tag-good" : "tag-mute"}`}>{row.is_active ? "Active" : "Disabled"}</span>
                  ) : (
                    <span className="tag tag-warn">Waiting for approval</span>
                  )}
                </div>
                <select className="input" aria-label={`Role for ${row.email}`} value={row.role} onChange={(e) => void change(row.id, { role: e.target.value as RoleName })}>
                  {ROLES.map((role) => (
                    <option key={role} value={role}>{ROLE_LABEL[role]}</option>
                  ))}
                </select>
                <div className="row-actions">
                  {!row.is_approved && <button className="btn btn-primary btn-sm" onClick={() => void change(row.id, { is_approved: true })}>Approve</button>}
                  {row.is_approved && row.id !== me?.id && (
                    <button className="btn btn-ghost btn-sm" onClick={() => void change(row.id, { is_active: !row.is_active })}>
                      {row.is_active ? "Disable" : "Enable"}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
      <section className="panel panel-pad" style={{ marginTop: 20 }}>
        <div className="panel-head"><h2>What each role can do</h2></div>
        <ul className="plain-list">
          {ROLES.map((role) => (
            <li key={role}><strong>{ROLE_LABEL[role]}</strong> — {ROLE_HELP[role]}</li>
          ))}
        </ul>
      </section>
    </RequireRole>
  );
}
