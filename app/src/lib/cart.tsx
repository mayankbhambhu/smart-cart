import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react";
import { Alert } from "react-native";
import { api } from "./api";
import { useAuth } from "./auth";
import type { Cart } from "./types";

type CartState = { cart: Cart | null; refresh: () => Promise<void>; setQty: (productId: number, q: number) => Promise<void>;
  setup: (storeId: number, mode: Cart["mode"]) => Promise<void>; replace: (c: Cart) => void;
  addFromStore: (storeId: number, productId: number) => Promise<string> };
const Ctx = createContext<CartState | null>(null);

export function CartProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [cart, setCart] = useState<Cart | null>(null);
  const refresh = useCallback(async () => { setCart(await api.get<Cart>("/cart")); }, []);
  useEffect(() => { if (user?.role === "customer") refresh().catch(() => {}); else setCart(null); }, [user, refresh]);

  const setQty = async (productId: number, quantity: number) => {
    try { setCart(await api.put<Cart>(`/cart/items/${productId}`, { quantity: Math.max(0, quantity) })); }
    catch (e) { Alert.alert("Cart", (e as Error).message); }
  };
  const setup = async (store_id: number, mode: Cart["mode"]) => setCart(await api.post<Cart>("/cart/setup", { store_id, mode }));
  /** "Add" on a stock-check result. The cart belongs to one store, so an item from another store moves
   *  the cart there first (as pickup), unless a Scan & Go trip is in progress. Returns a message to show. */
  const addFromStore = async (storeId: number, productId: number) => {
    let current = await api.get<Cart>("/cart");
    let note = "";
    if (current.store_id !== storeId) {
      if (current.mode === "instore" && current.items.length) {
        throw new Error(`You're shopping in-store at ${current.store_name}. Check out or empty that cart before adding items from another store.`);
      }
      const before = current.item_count;
      current = await api.post<Cart>("/cart/setup", { store_id: storeId, mode: current.mode === "instore" ? "pickup" : current.mode });
      note = ` Your cart is now at ${current.store_name}.`;
      if (current.item_count < before) note += " Items that store doesn't stock were removed.";
    }
    const updated = await api.post<Cart>("/cart/items", { product_id: productId, quantity: 1 });
    setCart(updated);
    return `${updated.item_count} item${updated.item_count === 1 ? "" : "s"} in your cart.${note}`;
  };
  return <Ctx.Provider value={{ cart, refresh, setQty, setup, replace: setCart, addFromStore }}>{children}</Ctx.Provider>;
}

export function useCart() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useCart must be inside CartProvider");
  return v;
}
