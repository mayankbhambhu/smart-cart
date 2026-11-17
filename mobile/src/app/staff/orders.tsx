import { useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { Alert, FlatList, RefreshControl, Text, View } from "react-native";
import { Chip } from "@/components/Chip";
import { Badge, Button, Card, Muted, Row, s } from "@/components/ui";
import { api, logError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useLive } from "@/lib/live";
import { colors, inr, nice, when } from "@/lib/theme";

type StoreOrder = { id: number; number: string; customer: string; fulfilment: string; status: string; total: number; paid_at: string;
  pickup_slot: string | null; items: { name: string; quantity: number; location: string }[] };

const NEXT: Record<string, (o: StoreOrder) => string | null> = {
  preparing: (o) => (o.fulfilment === "pickup" ? "ready" : "out_for_delivery"),
  out_for_delivery: () => "completed", ready: () => "completed",
};

/** Pickup and delivery orders with their pick list; move them through their statuses. */
export default function StaffOrders() {
  const { user } = useAuth();
  const sid = user!.store_id!;
  const [rows, setRows] = useState<StoreOrder[]>([]);
  const [filter, setFilter] = useState("open");
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const all = await api.get<StoreOrder[]>(`/ops/stores/${sid}/orders`);
      setRows(filter === "open" ? all.filter((o) => NEXT[o.status]) : all.slice(0, 60));
    } catch (e) { logError(e); } finally { setLoading(false); }
  }, [sid, filter]);
  useFocusEffect(useCallback(() => { load(); }, [load]));
  useLive([`store:${sid}`], (e) => { if (e.event === "order_paid" || e.event === "order_status") load(); });

  const advance = async (o: StoreOrder, status: string) => {
    try { await api.post(`/ops/stores/${sid}/orders/${o.id}/status`, { status }); load(); }
    catch (e) { Alert.alert("Order", (e as Error).message); }
  };

  return (
    <View style={s.screen}>
      <Row style={{ padding: 12, paddingBottom: 4 }}><Chip label="To prepare / hand over" active={filter === "open"} onPress={() => setFilter("open")} /><Chip label="Recent" active={filter === "all"} onPress={() => setFilter("all")} /></Row>
      <FlatList data={rows} keyExtractor={(o) => String(o.id)} contentContainerStyle={{ padding: 12, paddingBottom: 40 }}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
        ListEmptyComponent={<Muted>No orders waiting.</Muted>}
        renderItem={({ item: o }) => {
          const next = NEXT[o.status]?.(o);
          return (
            <Card>
              <Row style={{ justifyContent: "space-between" }}><Text style={{ fontWeight: "800" }}>{o.number}</Text><Badge text={nice(o.status)} tone={next ? "warn" : "ok"} /></Row>
              <Muted>{o.customer} · {nice(o.fulfilment)} · {inr(o.total)}{o.pickup_slot ? ` · pickup ${when(o.pickup_slot)}` : ""}</Muted>
              {o.items.map((i, k) => <Text key={k} style={{ fontSize: 13 }}>{i.quantity}× {i.name} <Text style={{ color: colors.info }}>{i.location}</Text></Text>)}
              {next && <Button small title={`Mark ${nice(next)}`} style={{ marginTop: 8 }} onPress={() => advance(o, next)} />}
            </Card>);
        }} />
    </View>
  );
}
