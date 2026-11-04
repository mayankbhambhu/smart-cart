import Constants from "expo-constants";

type Extra = { apiUrl?: string; stripePublishableKey?: string; googleClientIds?: { ios?: string; android?: string; web?: string } };
const extra = (Constants.expoConfig?.extra ?? {}) as Extra;

/** API base URL. On a physical phone use your computer's LAN IP, e.g. EXPO_PUBLIC_API_URL=http://192.168.1.20:8000 */
export const API_URL = process.env.EXPO_PUBLIC_API_URL ?? extra.apiUrl ?? "http://localhost:8000";
export const STRIPE_KEY = process.env.EXPO_PUBLIC_STRIPE_KEY ?? extra.stripePublishableKey ?? "";
export const GOOGLE_IDS = extra.googleClientIds ?? {};
