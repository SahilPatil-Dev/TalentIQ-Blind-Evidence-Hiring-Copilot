"use client";
/**
 * AuthProvider.tsx — knows who is signed in.
 *
 *   const { user, loading, signIn, signOut } = useAuth();
 *
 * On start it asks the API "who am I?" if a token exists. If the session ends
 * (token expired), api.ts fires an event and we send the user to /login.
 */
import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, SIGNED_OUT_EVENT, tokenStore, type User } from "@/lib/api";

interface AuthState {
  user: User | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthState>({
  user: null,
  loading: true,
  signIn: async () => {},
  signOut: async () => {},
});

export function useAuth() {
  return useContext(AuthContext);
}

export const PUBLIC_PATHS = ["/login", "/register"];

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  // Restore the session when the page first opens.
  useEffect(() => {
    if (!tokenStore.get()) {
      setLoading(false);
      return;
    }
    api
      .me()
      .then(setUser)
      .catch(() => tokenStore.clear())
      .finally(() => setLoading(false));
  }, []);

  // The session ended somewhere (expired or signed out): go to the sign-in page.
  useEffect(() => {
    const onSignedOut = () => {
      setUser(null);
      router.replace("/login");
    };
    window.addEventListener(SIGNED_OUT_EVENT, onSignedOut);
    return () => window.removeEventListener(SIGNED_OUT_EVENT, onSignedOut);
  }, [router]);

  // Pages other than login, register and the landing page ("/") need a signed-in user.
  useEffect(() => {
    if (!loading && !user && pathname !== "/" && !PUBLIC_PATHS.includes(pathname)) router.replace("/login");
  }, [loading, user, pathname, router]);

  const signIn = useCallback(async (email: string, password: string) => {
    const result = await api.login(email, password);
    tokenStore.set(result.token);
    setUser(result.user);
  }, []);

  const signOut = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      /* the token may already be gone: still sign out locally */
    }
    tokenStore.clear();
    setUser(null);
    router.replace("/login");
  }, [router]);

  return <AuthContext.Provider value={{ user, loading, signIn, signOut }}>{children}</AuthContext.Provider>;
}
