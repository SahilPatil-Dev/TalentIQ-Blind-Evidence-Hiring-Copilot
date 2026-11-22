"use client";
/**
 * register/page.tsx ("/register") — create an account.
 * The very first account becomes the administrator. Everyone after that waits for
 * an administrator to approve them and choose their role.
 */
import Link from "next/link";
import { useState } from "react";
import { Brand } from "@/components/Sidebar";
import { api } from "@/lib/api";

export default function RegisterPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await api.register({ name, email, password });
      setDone(result.message);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not create the account.");
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <div className="panel panel-pad auth-card">
        <Brand />
        <h1>Account created</h1>
        <p>{done}</p>
        <Link href="/login" className="btn btn-primary btn-block">Go to sign in</Link>
      </div>
    );
  }

  return (
    <form className="panel panel-pad auth-card" onSubmit={submit}>
      <Brand />
      <h1>Create an account</h1>
      <label className="field">
        <span>Your name</span>
        <input className="input" required autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} />
      </label>
      <label className="field">
        <span>Work email</span>
        <input className="input" type="email" required autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} />
      </label>
      <label className="field">
        <span>Password <small>(at least 10 characters)</small></span>
        <input className="input" type="password" required minLength={10} autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />
      </label>
      {error && <p className="form-error" role="alert">{error}</p>}
      <button className="btn btn-primary btn-block" type="submit" disabled={busy}>
        {busy && <span className="spinner" />} {busy ? "Creating…" : "Create account"}
      </button>
      <p className="auth-alt">
        Already have an account? <Link href="/login">Sign in</Link>
      </p>
    </form>
  );
}
