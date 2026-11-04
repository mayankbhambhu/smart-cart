import { router, useFocusEffect } from "expo-router";
import * as Haptics from "expo-haptics";
import { useCallback, useState } from "react";
import { Alert, Pressable, ScrollView, Text, View } from "react-native";
import { StoreMap } from "@/components/StoreMap";
import { Badge, Button, Card, H1, H2, Input, Muted, Row, s, SummaryLine } from "@/components/ui";
import { api } from "@/lib/api";
import { useCart } from "@/lib/cart";
import { useLive } from "@/lib/live";
import { colors, inr } from "@/lib/theme";
import type { Cart, ListSummary, Route, Store } from "@/lib/types";

/** Scan & Go: family list -> optimised aisle route -> smart cart -> pay on phone -> walk out. */
export default function InStore() {
  const { cart, setup, replace, refresh } = useCart();
  const [stores, setStores] = useState<Store[]>([]);
  const [lists, setLists] = useState<ListSummary[]>([]);
  const [listId, setListId] = useState<number | null>(null);
  const [route, setRoute] = useState<Route | null>(null);
  const [code, setCode] = useState("");

  const loadRoute = useCallback(async (lid: number | null, storeId?: number) => {
    if (!lid || !storeId) return setRoute(null);
    setRoute(await api.get<Route>(`/lists/${lid}/route`, { store_id: storeId }));
  }, []);

  useFocusEffect(useCallback(() => {
    api.get<Store[]>("/stores").then(setStores);
    api.get<ListSummary[]>("/lists").then((ls) => {
      setLists(ls);
      const lid = listId ?? ls[0]?.id ?? null;
      setListId(lid);
      refresh().then(() => {});
      if (cart?.mode === "instore") loadRoute(lid, cart.store_id);
    });
  }, [cart?.mode, cart?.store_id]));

  // Family member adds "Milk" at home -> route re-plans live in the store.
  useLive(listId ? [`list:${listId}`] : [], (e) => {
    if (!e.channel.startsWith("list:")) return;
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    if (e.event === "item_added") Alert.alert("Family list updated", `${e.data.actor} added ${e.data.item}`);
    loadRoute(listId, cart?.store_id);
  });

  const pick = async (lid: number, itemId: number, productId: number, quantity: number) => {
    try {
      replace(await api.post<Cart>("/cart/items", { product_id: productId, quantity }));
      await api.patch(`/lists/${lid}/items/${itemId}`, { checked: true });
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
      loadRoute(lid, cart?.store_id);
    } catch (e) { Alert.alert("Could not add", (e as Error).message); }
  };

  const addCode = async () => {
    if (!code.trim() || !cart) return;
    try {
      const isBarcode = /^\d{8,}$/.test(code.trim());
      let body: object = { barcode: code.trim() };
      if (!isBarcode) {
        const hits = await api.get<{ id: number }[]>(`/stores/${cart.store_id}/products`, { q: code, in_stock_only: true, limit: 1 });
        if (!hits.length) return Alert.alert("Not found", `No product matches "${code}"`);
        body = { product_id: hits[0].id };
      }
      replace(await api.post<Cart>("/cart/items", body));
      setCode("");
    } catch (e) { Alert.alert("Could not add", (e as Error).message); }
  };

  if (!cart || cart.mode !== "instore") {
    return (
      <ScrollView style={s.screen} contentContainerStyle={s.pad}>
        <H1>📱 Scan & Go</H1>
        <Muted>Shop the aisles with your phone. We route you through the store from your family list, you scan items into your smart cart, pay with Apple Pay / Google Pay / UPI, and scan your receipt at the exit gate. No queues, no cashier.</Muted>
        <H2>Which store are you in?</H2>
        {stores.map((st) => <Button key={st.id} title={st.name} variant="secondary" style={{ marginBottom: 8 }} onPress={() => setup(st.id, "instore")} />)}
      </ScrollView>
    );
  }

  const done = new Set<number>();
  return (
    <ScrollView style={s.screen} contentContainerStyle={[s.pad, { paddingBottom: 140 }]}>
      <H1>{cart.store_name}</H1>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 10 }}>
        {lists.map((l) => (
          <Pressable key={l.id} onPress={() => { setListId(l.id); loadRoute(l.id, cart.store_id); }}
            style={{ marginRight: 6, paddingHorizontal: 12, paddingVertical: 6, borderRadius: 999, backgroundColor: l.id === listId ? colors.brand : colors.surface, borderWidth: 1, borderColor: colors.line }}>
            <Text style={{ color: l.id === listId ? "#fff" : colors.ink2, fontWeight: "700" }}>📝 {l.name}</Text></Pressable>))}
      </ScrollView>
      {route && (
        <Card>
          <Row style={{ justifyContent: "space-between" }}><H2>Your route</H2><Muted>{route.total_distance_m} m · ~{route.estimated_minutes} min</Muted></Row>
          <StoreMap route={route} done={done} />
          {route.steps.map((st) => (
            <View key={st.step} style={{ paddingVertical: 10, borderBottomWidth: 1, borderColor: colors.line }}>
              <Text style={{ fontWeight: "800", color: colors.ink }}>{st.step}. Aisle {st.aisle}, Row {st.row} <Text style={{ color: colors.muted, fontWeight: "400" }}>· {st.distance_from_previous_m} m</Text></Text>
              {st.items.map((it) => (
                <Row key={it.key} style={{ justifyContent: "space-between", marginTop: 6 }}>
                  <Text style={{ flex: 1 }}>{it.label} · {inr(it.price)}</Text>
                  <Button small title="Picked ✓" onPress={() => pick(listId!, it.list_item_id!, it.product_id, it.quantity ?? 1)} />
                </Row>))}
            </View>))}
          {!route.steps.length && <Muted>Everything on the list is in your cart. Head to the exit and check out. 🎉</Muted>}
          {!!route.unavailable?.length && <Muted>Not available here: {route.unavailable.join(", ")}</Muted>}
        </Card>)}
      <Card>
        <H2>Smart cart</H2>
        <Row style={{ marginBottom: 10 }}>
          <Input placeholder="Barcode or item name" value={code} onChangeText={setCode} onSubmitEditing={addCode} style={{ flex: 1 }} />
          <Button small title="📷" variant="secondary" onPress={() => router.push("/scan")} />
          <Button small title="Add" onPress={addCode} />
        </Row>
        {cart.items.map((i) => <SummaryLine key={i.product_id} label={`${i.quantity}× ${i.name}`} value={inr(i.line_total)} />)}
        {!cart.items.length && <Muted>Nothing in your cart yet.</Muted>}
        {cart.discount > 0 && <SummaryLine label="Discount" value={`−${inr(cart.discount)}`} />}
        <SummaryLine label="GST" value={inr(cart.tax)} />
        <SummaryLine label="Total" value={inr(cart.total)} bold />
        <Badge text="Items leave shelf stock the moment they're in your cart" tone="info" />
      </Card>
      {!!cart.items.length && <Button title={`Checkout · ${inr(cart.total)}`} onPress={() => router.push("/cart")} />}
    </ScrollView>
  );
}
