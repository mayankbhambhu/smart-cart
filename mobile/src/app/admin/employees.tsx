import { useCallback, useEffect, useState } from "react";
import { Alert, FlatList, RefreshControl, Text, View } from "react-native";
import { Chip } from "@/components/Chip";
import { Badge, Button, Card, Input, Muted, Row, s } from "@/components/ui";
import { api, logError } from "@/lib/api";
import { ROLE_LABEL } from "@/lib/roles";
import { inr } from "@/lib/theme";

type Emp = { id: number; name: string; email: string; phone: string; role: string; employee_code: string | null; joined_on: string | null;
  left_on: string | null; hourly_wage: number | null; is_active: boolean; store_name: string | null };

export default function AdminEmployees() {
  const [q, setQ] = useState("");
  const [active, setActive] = useState(true);
  const [rows, setRows] = useState<Emp[]>([]);
  const [loading, setLoading] = useState(false);
  const load = useCallback(async () => {
    setLoading(true);
    try { setRows(await api.get<Emp[]>("/admin/employees", { q, active })); } catch (e) { logError(e); } finally { setLoading(false); }
  }, [q, active]);
  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t); }, [load]);

  const remove = (e: Emp) => Alert.alert(`Remove ${e.name}?`, "Their login stops working immediately. Attendance history is kept for payroll.", [
    { text: "Cancel", style: "cancel" },
    { text: "Left", onPress: () => doRemove(e, "left") },
    { text: "Fired", style: "destructive", onPress: () => doRemove(e, "fired") }]);
  const doRemove = async (e: Emp, reason: string) => {
    try { await api.del(`/admin/employees/${e.id}?reason=${reason}`); load(); } catch (err) { Alert.alert("Remove", (err as Error).message); }
  };
  const reset = async (e: Emp) => {
    try {
      const r = await api.post<{ login: string; temporary_password: string }>(`/admin/employees/${e.id}/reset-password`);
      Alert.alert("New temporary password", `${r.login}\n${r.temporary_password}\n\nShown once. They must change it at next login.`);
    } catch (err) { Alert.alert("Reset", (err as Error).message); }
  };

  return (
    <View style={s.screen}>
      <View style={{ padding: 12, paddingBottom: 0 }}>
        <Input placeholder="Search by name" value={q} onChangeText={setQ} />
        <Row style={{ marginTop: 8 }}><Chip label="Active" active={active} onPress={() => setActive(true)} /><Chip label="Removed" active={!active} onPress={() => setActive(false)} /></Row>
      </View>
      <FlatList data={rows} keyExtractor={(r) => String(r.id)} contentContainerStyle={{ padding: 12, paddingBottom: 40 }}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
        ListEmptyComponent={<Muted>No employees.</Muted>}
        renderItem={({ item: e }) => (
          <Card>
            <Row style={{ justifyContent: "space-between" }}><Text style={{ fontWeight: "800", flex: 1 }}>{e.name}</Text><Badge text={ROLE_LABEL[e.role] ?? e.role} /></Row>
            <Muted>{e.store_name} · {e.employee_code ?? "—"} · {e.phone}</Muted>
            <Muted>Joined {e.joined_on ?? "—"}{e.left_on ? ` · left ${e.left_on}` : ""} · {e.hourly_wage ? `${inr(e.hourly_wage)}/hr` : "—"}</Muted>
            {e.is_active && e.role !== "owner" && (
              <Row style={{ marginTop: 8 }}>
                <Button small variant="secondary" title="Reset password" onPress={() => reset(e)} />
                <Button small variant="danger" title="Remove" onPress={() => remove(e)} />
              </Row>)}
          </Card>)} />
    </View>
  );
}
