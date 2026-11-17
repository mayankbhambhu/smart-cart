import { useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { Alert, RefreshControl, ScrollView, Text, View } from "react-native";
import { Chip } from "@/components/Chip";
import { Badge, Button, Card, H2, Input, Muted, Row, s } from "@/components/ui";
import { api, logError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { ROLE_LABEL, SUPERVISORS } from "@/lib/roles";
import { colors, nice } from "@/lib/theme";

type Task = { id: number; title: string; description: string; priority: string; status: string; completion_note: string | null;
  manager_rating: number | null; assigned_to: { id: number; name: string; role: string } | null; assigned_by: { name: string } | null };
type Employee = { id: number; name: string; role: string; is_active: boolean; open_tasks: number; on_clock: boolean };

const CAN_ASSIGN: Record<string, string[]> = { owner: ["store_manager", "floor_manager", "worker"], store_manager: ["floor_manager", "worker"], floor_manager: ["worker"] };
const tone = (st: string) => (st === "done" ? "info" : st === "reviewed" ? "ok" : "warn") as "info" | "ok" | "warn";

export default function StaffTasks() {
  const { user } = useAuth();
  const sid = user!.store_id!;
  const supervisor = SUPERVISORS.includes(user!.role);
  const [mine, setMine] = useState<Task[]>([]);
  const [toReview, setToReview] = useState<Task[]>([]);
  const [team, setTeam] = useState<Employee[]>([]);
  const [notes, setNotes] = useState<Record<number, string>>({});
  const [ratings, setRatings] = useState<Record<number, number>>({});
  const [form, setForm] = useState({ title: "", assignee: 0, priority: "normal" });
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setMine(await api.get<Task[]>("/ops/me/tasks"));
      if (supervisor) {
        setToReview(await api.get<Task[]>(`/ops/stores/${sid}/tasks`, { status: "done" }));
        const allowed = CAN_ASSIGN[user!.role] ?? [];
        setTeam((await api.get<Employee[]>(`/ops/stores/${sid}/employees`)).filter((e) => e.is_active && allowed.includes(e.role)));
      }
    } catch (e) { logError(e); } finally { setLoading(false); }
  }, [sid, supervisor, user]);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  const run = async (fn: () => Promise<unknown>, ok: string) => {
    try { await fn(); Alert.alert(ok); load(); } catch (e) { Alert.alert("Tasks", (e as Error).message); }
  };

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.pad} refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />} keyboardShouldPersistTaps="handled">
      <H2>My tasks</H2>
      {mine.map((t) => (
        <Card key={t.id}>
          <Row style={{ justifyContent: "space-between" }}><Text style={{ fontWeight: "800", flex: 1 }}>{t.title}</Text><Badge text={nice(t.status)} tone={tone(t.status)} /></Row>
          {!!t.description && <Muted>{t.description}</Muted>}
          <Muted>Priority {t.priority} · from {t.assigned_by?.name}</Muted>
          {t.status === "assigned" && <Button small variant="secondary" title="Start" style={{ marginTop: 8 }} onPress={() => run(() => api.post(`/ops/me/tasks/${t.id}`, { status: "in_progress" }), "Task started")} />}
          {(t.status === "assigned" || t.status === "in_progress") && (
            <Row style={{ marginTop: 8 }}>
              <Input placeholder="What did you do?" value={notes[t.id] ?? ""} onChangeText={(v) => setNotes({ ...notes, [t.id]: v })} style={{ flex: 1 }} />
              <Button small title="Done" onPress={() => run(() => api.post(`/ops/me/tasks/${t.id}`, { status: "done", completion_note: notes[t.id] ?? "" }), "Marked done — your manager has been notified")} />
            </Row>)}
          {t.completion_note && <Muted>Your note: “{t.completion_note}”</Muted>}
          {t.manager_rating != null && <Text style={{ color: "#e0a800" }}>{"★".repeat(t.manager_rating)}</Text>}
        </Card>))}
      {!mine.length && <Muted>No tasks assigned to you.</Muted>}

      {supervisor && <>
        <H2>Completed work to review</H2>
        {toReview.map((t) => (
          <Card key={t.id}>
            <Text style={{ fontWeight: "800" }}>{t.title}</Text>
            <Muted>{t.assigned_to?.name} · “{t.completion_note}”</Muted>
            <Row style={{ marginTop: 8, flexWrap: "wrap" }}>
              {[1, 2, 3, 4, 5].map((n) => <Chip key={n} label={"★".repeat(n)} active={ratings[t.id] === n} onPress={() => setRatings({ ...ratings, [t.id]: n })} />)}
            </Row>
            <Button small title="Save review" disabled={!ratings[t.id]} onPress={() => run(() => api.post(`/ops/stores/${sid}/tasks/${t.id}/review`, { rating: ratings[t.id], feedback: "" }), "Review saved")} />
          </Card>))}
        {!toReview.length && <Muted>Nothing waiting for review.</Muted>}

        <Card style={{ marginTop: 12 }}>
          <H2>Assign a task</H2>
          <Input placeholder="e.g. Refill Aisle 4 chips" value={form.title} onChangeText={(v) => setForm({ ...form, title: v })} />
          <Text style={{ fontWeight: "700", marginTop: 10, marginBottom: 6 }}>Assign to</Text>
          <View style={{ flexDirection: "row", flexWrap: "wrap" }}>
            {team.map((e) => <Chip key={e.id} label={`${e.name} · ${ROLE_LABEL[e.role] ?? e.role}${e.on_clock ? " · on clock" : ""}`} active={form.assignee === e.id} onPress={() => setForm({ ...form, assignee: e.id })} />)}
          </View>
          <Row style={{ flexWrap: "wrap" }}>{["low", "normal", "high", "urgent"].map((p) => <Chip key={p} label={p} active={form.priority === p} onPress={() => setForm({ ...form, priority: p })} />)}</Row>
          <Button title="Assign & alert" disabled={!form.title || !form.assignee} style={{ marginTop: 8 }}
            onPress={() => run(async () => { await api.post(`/ops/stores/${sid}/tasks`, { title: form.title, assigned_to_id: form.assignee, priority: form.priority }); setForm({ title: "", assignee: 0, priority: "normal" }); }, "Task assigned — the employee has been alerted")} />
          <Muted>{team.length ? "" : "No one you can assign to right now."}</Muted>
        </Card>
      </>}
      <View style={{ height: 20 }} /><Text style={{ color: colors.muted, textAlign: "center" }}>Pull down to refresh</Text>
    </ScrollView>
  );
}
