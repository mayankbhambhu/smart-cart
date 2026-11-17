import { router, useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { RefreshControl, ScrollView, Text, View } from "react-native";
import { Chip } from "@/components/Chip";
import { Button, Card, H1, H2, Muted, Row, s } from "@/components/ui";
import { api, logError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useLive } from "@/lib/live";
import { colors, inr } from "@/lib/theme";

type Overview = {
  kpis: { net_sales: number; gross_profit: number; orders: number; margin_percent: number };
  counts: { stores: number; employees: number; customers: number; pending_requests: number; open_tickets: number };
  store_sales: { store_id: number; name: string; net_sales: number }[];
};

export default function AdminHome() {
  const { user } = useAuth();
  const [period, setPeriod] = useState("month");
  const [ov, setOv] = useState<Overview | null>(null);
  const [loading, setLoading] = useState(false);
  const load = useCallback(async () => {
    setLoading(true);
    try { setOv(await api.get<Overview>("/admin/overview", { period })); } catch (e) { logError(e); } finally { setLoading(false); }
  }, [period]);
  useFocusEffect(useCallback(() => { load(); }, [load]));
  useLive(["admin"], () => load());  // new credential request or store issue

  const max = Math.max(1, ...(ov?.store_sales.map((x) => x.net_sales) ?? [1]));
  return (
    <ScrollView style={s.screen} contentContainerStyle={s.pad} refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}>
      <H1>Hi {user!.full_name.split(" ")[0]} 👋</H1><Muted>Platform admin</Muted>
      <Row style={{ marginTop: 10, flexWrap: "wrap" }}>{["today", "week", "month", "year"].map((p) => <Chip key={p} label={p} active={period === p} onPress={() => setPeriod(p)} />)}</Row>
      {ov && <>
        <Card>
          <H2>All stores · {period}</H2>
          {[["Net sales", inr(ov.kpis.net_sales)], ["Gross profit", `${inr(ov.kpis.gross_profit)} (${ov.kpis.margin_percent}%)`], ["Orders", String(ov.kpis.orders)]].map(([l, v]) => (
            <Row key={l} style={{ justifyContent: "space-between", paddingVertical: 3 }}><Muted>{l}</Muted><Text style={{ fontWeight: "800" }}>{v}</Text></Row>))}
        </Card>
        <Card>
          <H2>Needs attention</H2>
          <Row style={{ justifyContent: "space-between" }}>
            <Button small variant={ov.counts.pending_requests ? "primary" : "secondary"} title={`${ov.counts.pending_requests} credential requests`} onPress={() => router.push("/admin/requests")} />
            <Button small variant={ov.counts.open_tickets ? "primary" : "secondary"} title={`${ov.counts.open_tickets} open issues`} onPress={() => router.push("/admin/issues")} />
          </Row>
          <Muted>{ov.counts.stores} stores · {ov.counts.employees} employees · {ov.counts.customers} customers</Muted>
        </Card>
        <Card>
          <H2>Net sales by store</H2>
          {ov.store_sales.map((st) => (
            <View key={st.store_id} style={{ marginBottom: 8 }}>
              <Row style={{ justifyContent: "space-between" }}><Text>{st.name}</Text><Text style={{ fontWeight: "700" }}>{inr(st.net_sales)}</Text></Row>
              <View style={{ height: 8, borderRadius: 4, backgroundColor: colors.surface2 }}>
                <View style={{ height: 8, borderRadius: 4, backgroundColor: colors.brand, width: `${(100 * st.net_sales) / max}%` }} />
              </View>
            </View>))}
        </Card>
      </>}
    </ScrollView>
  );
}
