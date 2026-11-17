import { router, useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { Alert, RefreshControl, ScrollView, Text, View } from "react-native";
import { Badge, Button, Card, H1, H2, Muted, Row, s } from "@/components/ui";
import { api, logError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useLive } from "@/lib/live";
import { MANAGERS, ROLE_LABEL } from "@/lib/roles";
import { colors, inr, when } from "@/lib/theme";

type Alert_ = { id: number; product: string; aisle: number; row: number; quantity_now: number; status: string };
type MyTask = { id: number; title: string; priority: string; status: string };
type Clock = { on_clock: boolean; since: string | null };
type Kpis = { net_sales: number; gross_profit: number; orders: number; avg_basket: number; margin_percent: number };

export default function StaffHome() {
  const { user } = useAuth();
  const sid = user!.store_id!;
  const manager = MANAGERS.includes(user!.role);
  const [store, setStore] = useState<{ name: string } | null>(null);
  const [clock, setClock] = useState<Clock | null>(null);
  const [alerts, setAlerts] = useState<Alert_[]>([]);
  const [tasks, setTasks] = useState<MyTask[]>([]);
  const [kpis, setKpis] = useState<Kpis | null>(null);
  const [feed, setFeed] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [st, ck, al, tk] = await Promise.all([
        api.get<{ name: string }>(`/stores/${sid}`), api.get<Clock>("/ops/me/attendance"),
        api.get<Alert_[]>(`/ops/stores/${sid}/alerts`), api.get<MyTask[]>("/ops/me/tasks")]);
      setStore(st); setClock(ck); setAlerts(al); setTasks(tk.filter((t) => t.status === "assigned" || t.status === "in_progress"));
      if (manager) setKpis((await api.get<{ kpis: Kpis }>(`/ops/stores/${sid}/analytics`, { period: "today" })).kpis);
    } catch (e) { logError(e); } finally { setLoading(false); }
  }, [sid, manager]);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  useLive([`store:${sid}`], (e) => {
    const d = e.data;
    const line = { restock_alert: `Restock: ${d.product} (Aisle ${d.aisle}, Row ${d.row})`, order_paid: `New ${d.fulfilment} order ${d.number}`,
      gate: `Gate: ${d.reason}`, attendance: `${d.name} ${String(d.action).replace("_", " ")}`, task: "Task updated" }[e.event];
    if (line) setFeed((f) => [line, ...f].slice(0, 6));
    if (e.event === "restock_alert" || e.event === "task") load();
  });

  const toggleClock = async () => {
    try { const r = await api.post<{ action: string }>("/ops/me/clock"); Alert.alert(r.action === "clocked_in" ? "Clocked in" : "Clocked out"); load(); }
    catch (e) { Alert.alert("Clock", (e as Error).message); }
  };

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.pad} refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}>
      <H1>Hi {user!.full_name.split(" ")[0]} 👋</H1>
      <Muted>{ROLE_LABEL[user!.role]} · {store?.name ?? "…"}</Muted>
      <Card style={{ marginTop: 12 }}>
        <Row style={{ justifyContent: "space-between" }}>
          <View><H2>{clock?.on_clock ? "🟢 On the clock" : "⚪ Not clocked in"}</H2>{clock?.since && <Muted>since {when(clock.since)}</Muted>}</View>
          <Button small title={clock?.on_clock ? "Clock out" : "Clock in"} onPress={toggleClock} />
        </Row>
      </Card>
      {kpis && (
        <Card>
          <H2>Today</H2>
          <Row style={{ justifyContent: "space-between" }}>
            {[["Net sales", inr(kpis.net_sales)], ["Gross profit", inr(kpis.gross_profit)], ["Orders", String(kpis.orders)]].map(([l, v]) => (
              <View key={l}><Text style={{ fontSize: 18, fontWeight: "800", color: colors.ink }}>{v}</Text><Muted>{l}</Muted></View>))}
          </Row>
        </Card>)}
      <Card>
        <Row style={{ justifyContent: "space-between" }}><H2>⚠️ Restock alerts</H2><Button small variant="ghost" title="Inventory →" onPress={() => router.push("/staff/inventory")} /></Row>
        {alerts.slice(0, 5).map((a) => (
          <Row key={a.id} style={{ justifyContent: "space-between", paddingVertical: 5 }}>
            <Text style={{ flex: 1 }}>{a.product}{"\n"}<Text style={{ color: colors.muted, fontSize: 12 }}>Aisle {a.aisle}, Row {a.row} · {a.quantity_now} left</Text></Text>
            <Badge text={a.status} tone="warn" />
          </Row>))}
        {!alerts.length && <Muted>All shelves stocked.</Muted>}
      </Card>
      <Card>
        <Row style={{ justifyContent: "space-between" }}><H2>My open tasks</H2><Button small variant="ghost" title="Tasks →" onPress={() => router.push("/staff/tasks")} /></Row>
        {tasks.slice(0, 5).map((t) => <Text key={t.id} style={{ paddingVertical: 4 }}>• {t.title} <Text style={{ color: colors.muted }}>({t.priority})</Text></Text>)}
        {!tasks.length && <Muted>No open tasks 🎉</Muted>}
      </Card>
      <Card><H2>Live store activity</H2>{feed.length ? feed.map((f, i) => <Muted key={i}>{f}</Muted>) : <Muted>Sales, gate scans and alerts appear here live.</Muted>}</Card>
    </ScrollView>
  );
}
