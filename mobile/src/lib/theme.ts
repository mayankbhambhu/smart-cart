export const colors = {
  bg: "#f6f7f4", surface: "#ffffff", surface2: "#f1f3ee", ink: "#17201a", ink2: "#4b5650", muted: "#7a857e",
  line: "#e3e7e0", brand: "#1f8a4c", brandSoft: "#e3f4ea", info: "#2563eb", infoSoft: "#e6efff",
  danger: "#c8372d", dangerSoft: "#fde8e6", warn: "#b7791f", warnSoft: "#fff4dc",
};
export const radius = 14;
export const inr = (v: number | null | undefined) =>
  v == null ? "—" : "₹" + v.toLocaleString("en-IN", { maximumFractionDigits: 2, minimumFractionDigits: v % 1 ? 2 : 0 });
export const when = (iso: string | null) => (iso ? new Date(iso).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" }) : "—");
export const nice = (s: string | null | undefined) => (s ?? "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
export const CATEGORY_ICON: Record<number, string> = { 1: "🥦", 2: "🥛", 3: "🌾", 4: "🍿", 5: "🧃", 6: "🥣", 7: "🍪", 8: "🧴", 9: "🧽", 10: "🍗" };
