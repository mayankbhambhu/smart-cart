import * as Linking from "expo-linking";
import { router } from "expo-router";
import * as WebBrowser from "expo-web-browser";
import { Alert } from "react-native";
import { api } from "./api";
import { API_URL } from "./config";
import { APP_LABEL, appFor, homeHref, ROLE_LABEL } from "./roles";
import type { TokenOut } from "./types";

export type Providers = {
  google: { enabled: boolean; web_client_id: string | null };
  apple: { enabled: boolean };
  firebase_email_link: { enabled: boolean; continue_url: string; config: { apiKey: string; authDomain: string; projectId: string } | null };
  sso: { enabled: boolean; label: string };
};
export const fetchProviders = () => api.get<Providers>("/auth/providers");

/** Every sign-in method ends here: save the session, then the account's role decides which app opens. */
export async function completeSignIn(signIn: (p: TokenOut) => Promise<void>, payload: TokenOut) {
  await signIn(payload);
  const u = payload.user;
  if (u.must_change_password) return router.replace("/change-password");
  if (appFor(u.role) !== "shopper")
    Alert.alert(`Welcome, ${u.full_name.split(" ")[0] || "there"}`, `Signed in as ${ROLE_LABEL[u.role] ?? u.role} · opening ${APP_LABEL[appFor(u.role)]}`);
  router.replace(homeHref(u.role));
}

/** Single sign-on in the system browser. Only a one-time code comes back; it is swapped for a session. */
export async function signInWithSso(): Promise<TokenOut> {
  const back = Linking.createURL("sso");
  const res = await WebBrowser.openAuthSessionAsync(`${API_URL}/auth/sso/start?redirect=${encodeURIComponent(back)}`, back);
  if (res.type !== "success") throw new Error("Sign-in was cancelled");
  return exchangeFromUrl(res.url);
}

export async function exchangeFromUrl(url: string): Promise<TokenOut> {
  const q = Linking.parse(url).queryParams ?? {};
  if (q.error) throw new Error(String(q.error));
  if (!q.code) throw new Error("Sign-in did not complete");
  return api.post<TokenOut>("/auth/exchange", { code: String(q.code) });
}
