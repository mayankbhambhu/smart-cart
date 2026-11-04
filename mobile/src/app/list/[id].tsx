import * as Haptics from "expo-haptics";
import { router, Stack, useLocalSearchParams } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { Alert, Pressable, ScrollView, Share, Text, View } from "react-native";
import { Button, Card, Input, Muted, Row, s, SummaryLine } from "@/components/ui";
import { api } from "@/lib/api";
import { useCart } from "@/lib/cart";
import { useLive } from "@/lib/live";
import { colors, inr } from "@/lib/theme";
import type { ShoppingList } from "@/lib/types";

/** Collaborative list: edits from any family member appear instantly over WebSocket. */
export default function ListDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { cart, refresh: refreshCart } = useCart();
  const [list, setList] = useState<ShoppingList | null>(null);
  const [name, setName] = useState("");
  const [feed, setFeed] = useState<string[]>([]);

  const load = useCallback(async () => setList(await api.get<ShoppingList>(`/lists/${id}`, { store_id: cart?.store_id })), [id, cart?.store_id]);
  useEffect(() => { load(); }, [load]);
  useLive([`list:${id}`], (e) => {
    if (!e.channel.startsWith("list:")) return;
    Haptics.selectionAsync();
    setFeed((f) => [`${e.data.actor} · ${e.event.replace("_", " ")}${e.data.item ? `: ${e.data.item}` : ""}`, ...f].slice(0, 5));
    load();
  });

  if (!list) return null;
  const add = async () => { if (name.trim()) { await api.post(`/lists/${id}/items`, { name }); setName(""); load(); } };
  const toggle = async (itemId: number, checked: boolean) => { await api.patch(`/lists/${id}/items/${itemId}`, { checked }); load(); };
  const remove = async (itemId: number) => { await api.del(`/lists/${id}/items/${itemId}`); load(); };

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.pad}>
      <Stack.Screen options={{ title: list.name }} />
      <Muted>Shared with {list.members.map((m) => m.name).join(", ")}</Muted>
      <Row style={{ marginVertical: 10 }}>
        <Button small title="🧭 Shop in store" onPress={() => router.push("/(tabs)/instore")} />
        <Button small variant="secondary" title="🛒 Order all" onPress={async () => {
          const r = await api.post<{ skipped: string[] }>(`/cart/from-list/${id}`); await refreshCart();
          if (r.skipped.length) Alert.alert("Some items unavailable", r.skipped.join(", "));
          router.push("/cart"); }} />
        <Button small variant="ghost" title="Invite" onPress={() => Share.share({ message: `Join our FreshFlow list "${list.name}" with code ${list.invite_code}` })} />
      </Row>
      <Card>
        <Row style={{ marginBottom: 8 }}><Input placeholder="Add item, e.g. Milk" value={name} onChangeText={setName} onSubmitEditing={add} style={{ flex: 1 }} /><Button small title="Add" onPress={add} /></Row>
        {list.items.map((i) => (
          <Row key={i.id} style={{ paddingVertical: 8, borderBottomWidth: 1, borderColor: colors.line }}>
            <Pressable onPress={() => toggle(i.id, !i.checked)} style={{ width: 26, height: 26, borderRadius: 13, borderWidth: 2, borderColor: colors.brand, backgroundColor: i.checked ? colors.brand : "#fff", alignItems: "center", justifyContent: "center" }}>
              {i.checked && <Text style={{ color: "#fff", fontWeight: "900" }}>✓</Text>}</Pressable>
            <View style={{ flex: 1 }}>
              <Text style={{ fontWeight: "700", textDecorationLine: i.checked ? "line-through" : "none", color: i.checked ? colors.muted : colors.ink }}>{i.name} × {i.quantity}</Text>
              <Text style={{ fontSize: 12, color: colors.muted }}>{i.location ? `📍 ${i.location}` : "not in catalogue"} · by {i.added_by}</Text>
            </View>
            {i.price ? <Text>{inr(i.price * i.quantity)}</Text> : null}
            <Pressable onPress={() => remove(i.id)}><Text style={{ color: colors.muted, padding: 6 }}>✕</Text></Pressable>
          </Row>))}
        {list.estimated_total != null && <SummaryLine label="Estimated total" value={inr(list.estimated_total)} bold />}
      </Card>
      {!!feed.length && <Card><Text style={{ fontWeight: "700", marginBottom: 4 }}>Live activity</Text>{feed.map((f, i) => <Muted key={i}>{f}</Muted>)}</Card>}
    </ScrollView>
  );
}
