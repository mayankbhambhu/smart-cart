import { useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { Alert, FlatList, RefreshControl, Text, View } from "react-native";
import { Chip } from "@/components/Chip";
import { Badge, Button, Card, Input, Muted, Row, s } from "@/components/ui";
import { api, logError } from "@/lib/api";
import { nice, when } from "@/lib/theme";

type Ticket = { id: number; subject: string; description: string; category: string; priority: string; status: string;
  admin_response: string | null; store_name: string; raised_by: string; created_at: string };

/** Issues raised by stores; replying notifies the store. */
export default function AdminIssues() {
  const [status, setStatus] = useState("open");
  const [rows, setRows] = useState<Ticket[]>([]);
  const [reply, setReply] = useState<Record<number, string>>({});
  const [loading, setLoading] = useState(false);
  const load = useCallback(async () => {
    setLoading(true);
    try { setRows(await api.get<Ticket[]>("/admin/tickets", { status: status === "all" ? undefined : status })); } catch (e) { logError(e); } finally { setLoading(false); }
  }, [status]);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  const update = async (t: Ticket, newStatus: string) => {
    try { await api.post(`/admin/tickets/${t.id}`, { status: newStatus, admin_response: reply[t.id] ?? t.admin_response ?? "" }); Alert.alert("Store notified"); load(); }
    catch (e) { Alert.alert("Issue", (e as Error).message); }
  };

  return (
    <View style={s.screen}>
      <Row style={{ padding: 12, paddingBottom: 0, flexWrap: "wrap" }}>
        {["open", "in_progress", "resolved", "all"].map((st) => <Chip key={st} label={nice(st)} active={status === st} onPress={() => setStatus(st)} />)}
      </Row>
      <FlatList data={rows} keyExtractor={(r) => String(r.id)} contentContainerStyle={{ padding: 12, paddingBottom: 40 }}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
        ListEmptyComponent={<Muted>No issues here.</Muted>}
        renderItem={({ item: t }) => (
          <Card>
            <Row style={{ justifyContent: "space-between" }}><Text style={{ fontWeight: "800", flex: 1 }}>#{t.id} {t.subject}</Text><Badge text={t.priority} tone={t.priority === "urgent" || t.priority === "high" ? "danger" : "neutral"} /></Row>
            <Muted>{t.store_name} · {nice(t.category)} · {t.raised_by} · {when(t.created_at)}</Muted>
            <Text style={{ marginTop: 4 }}>{t.description}</Text>
            <Input placeholder="Reply to the store" multiline value={reply[t.id] ?? t.admin_response ?? ""} onChangeText={(v) => setReply({ ...reply, [t.id]: v })} style={{ marginTop: 8 }} />
            <Row style={{ marginTop: 8 }}>
              <Button small variant="secondary" title="In progress" onPress={() => update(t, "in_progress")} />
              <Button small title="Resolve" onPress={() => update(t, "resolved")} />
            </Row>
          </Card>)} />
    </View>
  );
}
