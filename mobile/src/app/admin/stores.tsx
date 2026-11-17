import { useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { Alert, FlatList, Pressable, RefreshControl, Text, View } from "react-native";
import { Badge, Button, Card, Muted, Row, s } from "@/components/ui";
import { api, logError } from "@/lib/api";
import { ROLE_LABEL } from "@/lib/roles";
import { colors, inr } from "@/lib/theme";

type StoreRow = { id: number; code: string; name: string; city: string; is_active: boolean; employee_count: number;
  monthly_wage_bill_estimate: number; owner: { name: string; phone: string; email: string } | null };
type Detail = { month_kpis: { net_sales: number; gross_profit: number; orders: number };
  employees: { id: number; name: string; role: string; phone: string; joined_on: string | null; hourly_wage: number | null; is_active: boolean }[] };

export default function AdminStores() {
  const [rows, setRows] = useState<StoreRow[]>([]);
  const [open, setOpen] = useState<number | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [loading, setLoading] = useState(false);
  const load = useCallback(async () => {
    setLoading(true);
    try { setRows(await api.get<StoreRow[]>("/admin/stores")); } catch (e) { logError(e); } finally { setLoading(false); }
  }, []);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  const expand = async (id: number) => {
    if (open === id) return setOpen(null);
    setOpen(id); setDetail(null);
    try { setDetail(await api.get<Detail>(`/admin/stores/${id}`)); } catch (e) { logError(e); }
  };
  const toggle = (st: StoreRow) => Alert.alert(st.is_active ? "Suspend store?" : "Activate store?", st.name, [
    { text: "Cancel", style: "cancel" },
    { text: st.is_active ? "Suspend" : "Activate", style: st.is_active ? "destructive" : "default", onPress: async () => {
      try { await api.post(`/admin/stores/${st.id}/toggle`); load(); } catch (e) { Alert.alert("Store", (e as Error).message); } } }]);

  return (
    <FlatList style={s.screen} data={rows} keyExtractor={(r) => String(r.id)} contentContainerStyle={s.pad}
      refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
      renderItem={({ item: st }) => (
        <Card>
          <Pressable onPress={() => expand(st.id)}>
            <Row style={{ justifyContent: "space-between" }}><Text style={{ fontWeight: "800", flex: 1 }}>{st.name}</Text><Badge text={st.is_active ? "active" : "suspended"} tone={st.is_active ? "ok" : "danger"} /></Row>
            <Muted>{st.code} · {st.city} · {st.employee_count} employees · wage bill ≈ {inr(st.monthly_wage_bill_estimate)}/month</Muted>
            {st.owner && <Muted>Owner: {st.owner.name} · {st.owner.phone}</Muted>}
          </Pressable>
          {open === st.id && detail && (
            <View style={{ marginTop: 8 }}>
              <Text style={{ fontWeight: "700" }}>This month: {inr(detail.month_kpis.net_sales)} net sales · {detail.month_kpis.orders} orders</Text>
              {detail.employees.filter((e) => e.is_active).map((e) => (
                <Text key={e.id} style={{ fontSize: 13, color: colors.ink2 }}>{e.name} · {ROLE_LABEL[e.role] ?? e.role} · {e.phone} · joined {e.joined_on ?? "—"} · {e.hourly_wage ? `${inr(e.hourly_wage)}/hr` : "—"}</Text>))}
            </View>)}
          <Row style={{ marginTop: 8 }}>
            <Button small variant="secondary" title={open === st.id ? "Hide details" : "Details"} onPress={() => expand(st.id)} />
            <Button small variant={st.is_active ? "danger" : "primary"} title={st.is_active ? "Suspend" : "Activate"} onPress={() => toggle(st)} />
          </Row>
        </Card>)} />
  );
}
