import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react";
import { api, loadToken, saveToken } from "./api";
import type { User } from "./types";

type AuthState = {
  user: User | null; ready: boolean;
  signIn: (payload: { access_token: string; user: User }) => Promise<void>;
  signOut: () => Promise<void>; refresh: () => Promise<void>;
};
const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  const refresh = useCallback(async () => {
    try { setUser(await api.get<User>("/me")); } catch { await saveToken(null); setUser(null); }
  }, []);

  useEffect(() => { (async () => { if (await loadToken()) await refresh(); setReady(true); })(); }, [refresh]);

  const signIn = async (p: { access_token: string; user: User }) => { await saveToken(p.access_token); setUser(p.user); };
  const signOut = async () => { await saveToken(null); setUser(null); };
  return <Ctx.Provider value={{ user, ready, signIn, signOut, refresh }}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth must be used inside AuthProvider");
  return v;
}
