import { router, useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { ScrollView, Text, View } from "react-native";
import { Chip } from "@/components/Chip";
import { Button, Card, H2, Muted, Row, s } from "@/components/ui";
import { api, logError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { MANAGERS, ROLE_LABEL, SUPERVISORS } from "@/lib/roles";
import { colors, inr, when } from "@/lib/theme";

type Shift = { id: number; label: string; starts_at: string; ends_at: string };
type Emp = { id: number; name: string; role: string; on_clock: boolean; open_tasks: number; is_active: boolean };
type Report = { kpis: { net_sales: number; gross_profit: number; orders: number; avg_basket: number; margin_percent: number };
  top_products: { name: string; units: number }[]; rush_hours: { label: string; orders: number }[] };

export default function StaffMore() {
  const { user, signOut } = useAuth();
  const sid = user!.store_id!;
  const manager = MANAGERS.includes(user!.role), supervisor = SUPERVISORS.includes(user!.role);
  const [shifts, setShifts] = useState<Shift[]>([]);
  const [team, setTeam] = useState<Emp[]>([]);
  const [period, setPeriod] = useState("today");
  const [report, setReport] = useState<Report | null>(null);

  const load = useCallback(async () => {
    try {
      setShifts(await api.get<Shift[]>("/ops/me/shifts"));
      if (supervisor) setTeam((await api.get<Emp[]>(`/ops/stores/${sid}/employees`)).filter((e) => e.is_active));
      if (manager) setReport(await api.get<Report>(`/ops/stores/${sid}/analytics`, { period }));
    } catch (e) { logError(e); }
  }, [sid, manager, supervisor, period]);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.pad}>
      <Button title="📷 Scan exit receipts (gate)" onPress={() => router.push("/staff/gate")} style={{ marginBottom: 12 }} />
      <Card>
        <H2>My upcoming shifts</H2>
        {shifts.slice(0, 5).map((sh) => <Text key={sh.id}>{sh.label || "Shift"} · {when(sh.starts_at)} – {new Date(sh.ends_at).toLocaleTimeString("en-IN", { timeStyle: "short" })}</Text>)}
        {!shifts.length && <Muted>No upcoming shifts.</Muted>}
      </Card>
      {manager && report && (
        <Card>
          <H2>Business analysis</H2>
          <Row style={{ flexWrap: "wrap" }}>{["today", "week", "month", "year"].map((p) => <Chip key={p} label={p} active={period === p} onPress={() => setPeriod(p)} />)}</Row>
          {[["Net sales", inr(report.kpis.net_sales)], ["Gross profit", `${inr(report.kpis.gross_profit)} (${report.kpis.margin_percent}%)`], ["Orders", String(report.kpis.orders)], ["Average basket", inr(report.kpis.avg_basket)]].map(([l, v]) => (
            <Row key={l} style={{ justifyContent: "space-between", paddingVertical: 3 }}><Muted>{l}</Muted><Text style={{ fontWeight: "800" }}>{v}</Text></Row>))}
          <Text style={{ fontWeight: "700", marginTop: 8 }}>Best sellers</Text>
          {report.top_products.slice(0, 5).map((p) => <Muted key={p.name}>{p.name} · {p.units} units</Muted>)}
          <Text style={{ fontWeight: "700", marginTop: 8 }}>Rush hours</Text>
          {report.rush_hours.map((h) => <Muted key={h.label}>{h.label} · {h.orders} orders</Muted>)}
          <Muted>Full charts are in the Store Operations website.</Muted>
        </Card>)}
      {supervisor && (
        <Card>
          <H2>Team</H2>
          {team.map((e) => (
            <Row key={e.id} style={{ justifyContent: "space-between", paddingVertical: 4 }}>
              <Text style={{ flex: 1 }}>{e.name}{"\n"}<Text style={{ color: colors.muted, fontSize: 12 }}>{ROLE_LABEL[e.role] ?? e.role} · {e.open_tasks} open tasks</Text></Text>
              <Text>{e.on_clock ? "🟢" : "⚪"}</Text>
            </Row>))}
        </Card>)}
      <View style={{ gap: 8 }}>
        <Button variant="secondary" title="Change password" onPress={() => router.push("/change-password")} />
        <Button variant="danger" title="Log out" onPress={async () => { await signOut(); router.replace("/login"); }} />
      </View>
    </ScrollView>
  );
}
