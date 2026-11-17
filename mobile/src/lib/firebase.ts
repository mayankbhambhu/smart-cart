import * as Linking from "expo-linking";
import * as SecureStore from "expo-secure-store";
import { getApps, initializeApp } from "firebase/app";
import { Auth, initializeAuth, inMemoryPersistence, isSignInWithEmailLink, sendSignInLinkToEmail, signInWithEmailLink } from "firebase/auth";
import { Platform } from "react-native";
import type { Providers } from "./signin";

type FirebaseConfig = NonNullable<Providers["firebase_email_link"]["config"]>;
const EMAIL_KEY = "ff_magic_email";
let auth: Auth | null = null;

// Firebase only proves the email address here; the app's own session comes from our API.
function firebaseAuth(cfg: FirebaseConfig): Auth {
  if (!auth) auth = initializeAuth(getApps()[0] ?? initializeApp(cfg), { persistence: inMemoryPersistence });
  return auth;
}
const remember = async (email: string | null) => {
  if (Platform.OS === "web") { email ? globalThis.localStorage?.setItem(EMAIL_KEY, email) : globalThis.localStorage?.removeItem(EMAIL_KEY); return; }
  email ? await SecureStore.setItemAsync(EMAIL_KEY, email) : await SecureStore.deleteItemAsync(EMAIL_KEY);
};
export const rememberedEmail = async () =>
  Platform.OS === "web" ? globalThis.localStorage?.getItem(EMAIL_KEY) ?? null : SecureStore.getItemAsync(EMAIL_KEY);

/** Firebase emails a sign-in link. The link lands on our web page, which forwards it into this app. */
export async function sendMagicLink(cfg: FirebaseConfig, continueUrl: string, email: string) {
  const appLink = Linking.createURL("magic-link");
  await sendSignInLinkToEmail(firebaseAuth(cfg), email, {
    url: `${continueUrl}?app=${encodeURIComponent(appLink)}`, handleCodeInApp: true });
  await remember(email);
}

export class NeedEmailError extends Error {}

/** Confirm the link with Firebase and return its ID token (exchanged with our API for a session). */
export async function finishMagicLink(cfg: FirebaseConfig, link: string, email?: string): Promise<string> {
  const a = firebaseAuth(cfg);
  if (!isSignInWithEmailLink(a, link)) throw new Error("This sign-in link is invalid or has expired. Request a new one.");
  const address = email || (await rememberedEmail());
  if (!address) throw new NeedEmailError("Confirm the email address the link was sent to.");
  const cred = await signInWithEmailLink(a, address, link);
  const idToken = await cred.user.getIdToken();
  await a.signOut();
  await remember(null);
  return idToken;
}
