import Constants from "expo-constants";

type Extra = { apiUrl?: string; stripePublishableKey?: string; googleClientIds?: { ios?: string; android?: string; web?: string } };
const extra = (Constants.expoConfig?.extra ?? {}) as Extra;

/** During development the phone loads the app from your computer (e.g. "192.168.1.20:8081"),
 *  so the API is on that same computer at port 8000. No IP needs to be typed by hand. */
function apiFromDevServer(): string | undefined {
  const host = Constants.expoConfig?.hostUri?.split(":")[0];
  return host ? `http://${host}:8000` : undefined;
}

/** An explicit EXPO_PUBLIC_API_URL wins (used for production builds in eas.json), unless it
 *  is still the documentation placeholder "192.168.x.x". */
const fromEnv = process.env.EXPO_PUBLIC_API_URL;
const envUrl = fromEnv && !/\.x(\.|:|$)/i.test(fromEnv) ? fromEnv : undefined;

export const API_URL = envUrl ?? apiFromDevServer() ?? extra.apiUrl ?? "http://localhost:8000";
/** The customer website: holds the privacy policy and the delete-account page (Google Play needs both). */
export const WEB_URL = (process.env.EXPO_PUBLIC_WEB_URL || API_URL.replace(/:8000$/, ":8001")).replace(/\/$/, "");
export const PRIVACY_URL = `${WEB_URL}/privacy`;
export const STRIPE_KEY = process.env.EXPO_PUBLIC_STRIPE_KEY ?? extra.stripePublishableKey ?? "";
export const GOOGLE_IDS = {
  ios: process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID || extra.googleClientIds?.ios || "",
  android: process.env.EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID || extra.googleClientIds?.android || "",
  web: process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID || extra.googleClientIds?.web || "",
};
