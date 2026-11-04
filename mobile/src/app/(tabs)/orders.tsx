import { router, useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { FlatList, Pressable, RefreshControl, Text } from "react-native";
import { Badge, Card, Muted, Row, s } from "@/components/ui";
import { api } from "@/lib/api";
import { inr, nice, when } from "@/lib/theme";
import type { Order } from "@/lib/types";

const tone = (st: string) => (["completed", "paid"].includes(st) ? "ok" : st === "cancelled" ? "danger" : "warn") as "ok" | "danger" | "warn";

export default function Orders() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(false);
  const load = useCallback(() => { setLoading(true); api.get<Order[]>("/orders").then(setOrders).finally(() => setLoading(false)); }, []);
  useFocusEffect(load);
  return (
    <FlatList style={s.screen} contentContainerStyle={s.pad} data={orders} keyExtractor={(o) => String(o.id)}
      refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
      ListEmptyComponent={<Muted>No orders yet.</Muted>}
      renderItem={({ item: o }) => (
        <Pressable onPress={() => router.push(`/order/${o.id}`)}>
          <Card>
            <Row style={{ justifyContent: "space-between" }}><Text style={{ fontWeight: "800" }}>{o.number}</Text><Badge text={nice(o.status)} tone={tone(o.status)} /></Row>
            <Muted>{o.store_name} · {nice(o.fulfilment)} · {when(o.paid_at)}</Muted>
            <Row style={{ justifyContent: "space-between", marginTop: 6 }}><Muted>{o.items.length} items</Muted><Text style={{ fontWeight: "800" }}>{inr(o.total)}</Text></Row>
          </Card>
        </Pressable>)} />
  );
}
