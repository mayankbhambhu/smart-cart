import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react";
import { Alert } from "react-native";
import { api } from "./api";
import { useAuth } from "./auth";
import type { Cart } from "./types";

type CartState = { cart: Cart | null; refresh: () => Promise<void>; setQty: (productId: number, q: number) => Promise<void>;
  setup: (storeId: number, mode: Cart["mode"]) => Promise<void>; replace: (c: Cart) => void };
const Ctx = createContext<CartState | null>(null);

export function CartProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [cart, setCart] = useState<Cart | null>(null);
  const refresh = useCallback(async () => { setCart(await api.get<Cart>("/cart")); }, []);
  useEffect(() => { if (user) refresh().catch(() => {}); else setCart(null); }, [user, refresh]);

  const setQty = async (productId: number, quantity: number) => {
    try { setCart(await api.put<Cart>(`/cart/items/${productId}`, { quantity: Math.max(0, quantity) })); }
    catch (e) { Alert.alert("Cart", (e as Error).message); }
  };
  const setup = async (store_id: number, mode: Cart["mode"]) => setCart(await api.post<Cart>("/cart/setup", { store_id, mode }));
  return <Ctx.Provider value={{ cart, refresh, setQty, setup, replace: setCart }}>{children}</Ctx.Provider>;
}

export function useCart() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useCart must be inside CartProvider");
  return v;
}
