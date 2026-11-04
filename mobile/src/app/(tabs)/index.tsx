import { router, useFocusEffect } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { FlatList, Pressable, RefreshControl, ScrollView, Text, View } from "react-native";
import { ProductCard } from "@/components/ProductCard";
import { Button, Input, Row, s } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useCart } from "@/lib/cart";
import { colors, inr } from "@/lib/theme";
import type { Product, Store } from "@/lib/types";

type Category = { id: number; name: string; icon: string };

export default function Shop() {
  const { user } = useAuth();
  const { cart, setQty, setup, refresh } = useCart();
  const [q, setQ] = useState("");
  const [cat, setCat] = useState<number | null>(null);
  const [diet, setDiet] = useState(false);
  const [products, setProducts] = useState<Product[]>([]);
  const [cats, setCats] = useState<Category[]>([]);
  const [stores, setStores] = useState<Store[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => { api.get<Category[]>("/categories").then(setCats); api.get<Store[]>("/stores").then(setStores); }, []);
  useFocusEffect(useCallback(() => { refresh().catch(() => {}); }, [refresh]));

  const load = useCallback(async () => {
    if (!cart) return;
    setLoading(true);
    try {
      setProducts(await api.get<Product[]>(`/stores/${cart.store_id}/products`, {
        q, category_id: cat, tags: diet && user?.dietary_preferences.length ? user.dietary_preferences.join(",") : undefined }));
    } finally { setLoading(false); }
  }, [cart?.store_id, q, cat, diet, user]);
  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t); }, [load]);

  const inCart = Object.fromEntries((cart?.items ?? []).map((i) => [i.product_id, i.quantity]));
  const header = (
    <View style={{ padding: 10, gap: 10 }}>
      <View style={{ backgroundColor: colors.brand, borderRadius: 16, padding: 16 }}>
        <Text style={{ color: "#fff", fontSize: 20, fontWeight: "800" }}>Hi {user?.full_name.split(" ")[0] || "there"} 👋</Text>
        <Text style={{ color: "#e3f4ea" }}>{cart?.store_name} · {cart?.mode === "delivery" ? "Delivery in ~12 min" : cart?.mode === "pickup" ? "Store pickup" : "Shopping in store"}</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginTop: 10 }}>
          {stores.map((st) => (
            <Pressable key={st.id} onPress={() => setup(st.id, cart?.mode ?? "delivery")}
              style={{ backgroundColor: st.id === cart?.store_id ? "#fff" : "#ffffff33", borderRadius: 999, paddingHorizontal: 12, paddingVertical: 6, marginRight: 6 }}>
              <Text style={{ color: st.id === cart?.store_id ? colors.brand : "#fff", fontWeight: "700" }}>{st.name.replace("FreshFlow ", "")}</Text>
            </Pressable>))}
        </ScrollView>
        <Row style={{ marginTop: 8 }}>
          {(["delivery", "pickup", "instore"] as const).map((m) => (
            <Pressable key={m} onPress={() => cart && setup(cart.store_id, m)} style={{ flex: 1, backgroundColor: cart?.mode === m ? "#fff" : "#ffffff22", borderRadius: 10, padding: 8 }}>
              <Text style={{ textAlign: "center", fontWeight: "700", color: cart?.mode === m ? colors.brand : "#fff" }}>{{ delivery: "🚴 Delivery", pickup: "🏬 Pickup", instore: "📱 In store" }[m]}</Text>
            </Pressable>))}
        </Row>
      </View>
      <Input placeholder="Search products… or where is it in the store?" value={q} onChangeText={setQ} />
      <ScrollView horizontal showsHorizontalScrollIndicator={false}>
        <Chip label={diet ? "✓ My diet" : "My diet"} active={diet} onPress={() => setDiet(!diet)} />
        <Chip label="All" active={cat === null} onPress={() => setCat(null)} />
        {cats.map((c) => <Chip key={c.id} label={`${c.icon} ${c.name}`} active={cat === c.id} onPress={() => setCat(c.id)} />)}
      </ScrollView>
      <Pressable onPress={() => router.push("/stores")}><Text style={{ color: colors.brand, fontWeight: "700" }}>📍 Find a store / check stock before you leave →</Text></Pressable>
    </View>
  );

  return (
    <View style={s.screen}>
      <FlatList data={products} numColumns={2} keyExtractor={(p) => String(p.id)} ListHeaderComponent={header}
        contentContainerStyle={{ padding: 5, paddingBottom: 90 }} refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
        renderItem={({ item }) => <ProductCard p={item} qty={inCart[item.id] ?? 0} onChange={(n) => setQty(item.id, n)} />} />
      {!!cart?.item_count && (
        <Button title={`View cart · ${cart.item_count} items · ${inr(cart.total)}`} onPress={() => router.push("/cart")}
          style={{ position: "absolute", left: 16, right: 16, bottom: 16 }} />)}
    </View>
  );
}

const Chip = ({ label, active, onPress }: { label: string; active: boolean; onPress: () => void }) => (
  <Pressable onPress={onPress} style={{ paddingHorizontal: 12, paddingVertical: 7, borderRadius: 999, marginRight: 6, borderWidth: 1,
    borderColor: active ? colors.brand : colors.line, backgroundColor: active ? colors.brand : colors.surface }}>
    <Text style={{ color: active ? "#fff" : colors.ink2, fontWeight: "600" }}>{label}</Text>
  </Pressable>
);
