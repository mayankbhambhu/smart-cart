import { useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { Alert, FlatList, RefreshControl, Text, View } from "react-native";
import { Chip } from "@/components/Chip";
import { Badge, Button, Card, H2, Input, Muted, Row, s } from "@/components/ui";
import { api, logError } from "@/lib/api";
import { ROLE_LABEL } from "@/lib/roles";
import { colors, inr, nice } from "@/lib/theme";

type Req = { id: number; full_name: string; email: string; phone: string; role: string; hourly_wage: number; joining_date: string;
  notes: string; status: string; owner_note: string | null; admin_note: string | null; store_name: string; requested_by: string };
type Issued = { name: string; login: string; temporary_password: string; employee_code?: string };

/** Final step of new-staff onboarding: manager → owner → admin issues the login. */
export default function AdminRequests() {
  const [status, setStatus] = useState("pending_admin");
  const [rows, setRows] = useState<Req[]>([]);
  const [notes, setNotes] = useState<Record<number, string>>({});
  const [issued, setIssued] = useState<Issued | null>(null);
  const [loading, setLoading] = useState(false);
  const load = useCallback(async () => {
    setLoading(true);
    try { setRows(await api.get<Req[]>("/admin/credential-requests", { status })); } catch (e) { logError(e); } finally { setLoading(false); }
  }, [status]);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  const review = async (r: Req, decision: "approve" | "send_back" | "reject") => {
    const note = notes[r.id] ?? "";
    if (decision === "send_back" && !note.trim()) return Alert.alert("Send back", "Add a note telling the store what to change.");
    try {
      const res = await api.post<{ credentials?: { login: string; temporary_password: string; employee_code: string } }>(`/admin/credential-requests/${r.id}/review`, { decision, note });
      if (res.credentials) setIssued({ name: r.full_name, ...res.credentials });
      else Alert.alert(decision === "reject" ? "Rejected" : "Sent back to the store");
      load();
    } catch (e) { Alert.alert("Review", (e as Error).message); }
  };

  return (
    <View style={s.screen}>
      <Row style={{ padding: 12, paddingBottom: 0, flexWrap: "wrap" }}>
        {["pending_admin", "pending_owner", "changes_requested", "approved", "rejected"].map((st) => <Chip key={st} label={nice(st)} active={status === st} onPress={() => setStatus(st)} />)}
      </Row>
      {issued && (
        <Card style={{ margin: 12, borderColor: colors.brand, borderWidth: 2 }}>
          <H2>🔐 Credentials for {issued.name}</H2>
          <Muted>Shown once. Share securely; they must set a new password at first login.</Muted>
          <Text selectable style={{ marginTop: 6 }}>Login: <Text style={{ fontWeight: "800" }}>{issued.login}</Text></Text>
          <Text selectable>Temporary password: <Text style={{ fontWeight: "800" }}>{issued.temporary_password}</Text></Text>
          {issued.employee_code && <Text selectable>Employee code: {issued.employee_code}</Text>}
          <Button small variant="secondary" title="Done" style={{ marginTop: 8 }} onPress={() => setIssued(null)} />
        </Card>)}
      <FlatList data={rows} keyExtractor={(r) => String(r.id)} contentContainerStyle={{ padding: 12, paddingBottom: 40 }}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
        ListEmptyComponent={<Muted>Nothing here.</Muted>}
        renderItem={({ item: r }) => (
          <Card>
            <Row style={{ justifyContent: "space-between" }}><Text style={{ fontWeight: "800", flex: 1 }}>{r.full_name}</Text><Badge text={nice(r.status)} tone={r.status === "approved" ? "ok" : r.status === "rejected" ? "danger" : "warn"} /></Row>
            <Muted>{ROLE_LABEL[r.role] ?? r.role} · {r.store_name} · {inr(r.hourly_wage)}/hr · joins {r.joining_date}</Muted>
            <Muted>{r.email} · {r.phone}</Muted>
            {!!r.notes && <Muted>Manager ({r.requested_by}): {r.notes}</Muted>}
            {!!r.owner_note && <Muted>Owner: {r.owner_note}</Muted>}
            {!!r.admin_note && <Muted>Admin: {r.admin_note}</Muted>}
            {r.status === "pending_admin" && <>
              <Input placeholder="Note to the store (needed to send back)" value={notes[r.id] ?? ""} onChangeText={(v) => setNotes({ ...notes, [r.id]: v })} style={{ marginTop: 8 }} />
              <Row style={{ marginTop: 8 }}>
                <Button small title="Approve & issue" onPress={() => review(r, "approve")} />
                <Button small variant="secondary" title="Send back" onPress={() => review(r, "send_back")} />
                <Button small variant="danger" title="Reject" onPress={() => review(r, "reject")} />
              </Row>
            </>}
          </Card>)} />
    </View>
  );
}
