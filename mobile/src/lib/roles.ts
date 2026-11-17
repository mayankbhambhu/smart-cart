import type { Href } from "expo-router";

/** Which app an account opens, decided by the role stored on the account. */
export type AppKind = "shopper" | "staff" | "admin";

export const STAFF_ROLES = ["worker", "floor_manager", "store_manager", "owner"];
export const SUPERVISORS = ["floor_manager", "store_manager", "owner"];
export const MANAGERS = ["store_manager", "owner"];

export function appFor(role: string | undefined): AppKind {
  if (role === "admin") return "admin";
  if (role && STAFF_ROLES.includes(role)) return "staff";
  return "shopper";
}

export function homeHref(role: string | undefined): Href {
  return ({ shopper: "/(tabs)", staff: "/staff", admin: "/admin" } as const)[appFor(role)];
}

export const APP_LABEL: Record<AppKind, string> = { shopper: "Shopping app", staff: "Store operations", admin: "Admin" };
export const ROLE_LABEL: Record<string, string> = {
  customer: "Shopper", worker: "Floor Assistant", floor_manager: "Floor Manager",
  store_manager: "Store Manager", owner: "Store Owner", admin: "Platform Admin",
};
