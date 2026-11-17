import { useCallback, useEffect, useState } from "react";
import { Alert, FlatList, Pressable, RefreshControl, Text, View } from "react-native";
import { Chip } from "@/components/Chip";
import { Badge, Button, Input, Muted, Row, s } from "@/components/ui";
import { api, logError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useLive } from "@/lib/live";
import { colors } from "@/lib/theme";

type Inv = { id: number; name: string; sku: string; quantity: number; aisle: number; row: number; threshold: number; restock_to: number; low: boolean };

/** Live shelf stock with aisle/row; staff record restocks here. */
export default function StaffInventory() {
  const { user } = useAuth();
  const sid = user!.store_id!;
  const [rows, setRows] = useState<Inv[]>([]);
  const [q, setQ] = useState("");
  const [low, setLow] = useState(false);
  const [open, setOpen] = useState<number | null>(null);
  const [qty, setQty] = useState("");
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try { setRows(await api.get<Inv[]>(`/ops/stores/${sid}/inventory`, { q, low_only: low })); } catch (e) { logError(e); } finally { setLoading(false); }
  }, [sid, q, low]);
  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t); }, [load]);

  // Shelf stock changes from smart carts and other staff arrive live.
  useLive([`store:${sid}`], (e) => {
    if (e.event !== "inventory") return;
    setRows((rs) => rs.map((r) => (r.id === e.data.inventory_id ? { ...r, quantity: e.data.quantity, low: e.data.low } : r)));
  });

  const restock = async (r: Inv) => {
    const n = parseInt(qty, 10);
    if (!n || n < 1) return Alert.alert("Restock", "Enter how many units you added.");
    try {
      const res = await api.patch<{ quantity: number; low: boolean }>(`/ops/stores/${sid}/inventory/${r.id}`, { quantity_delta: n });
      setRows((rs) => rs.map((x) => (x.id === r.id ? { ...x, quantity: res.quantity, low: res.low } : x)));
      setOpen(null); setQty("");
    } catch (e) { Alert.alert("Restock", (e as Error).message); }
  };

  return (
    <View style={s.screen}>
      <View style={{ padding: 12 }}>
        <Input placeholder="Search product" value={q} onChangeText={setQ} />
        <Row style={{ marginTop: 8 }}><Chip label="All" active={!low} onPress={() => setLow(false)} /><Chip label="Low stock" active={low} onPress={() => setLow(true)} /></Row>
      </View>
      <FlatList data={rows} keyExtractor={(r) => String(r.id)} contentContainerStyle={{ paddingHorizontal: 12, paddingBottom: 40 }}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
        ListEmptyComponent={<Muted>No products.</Muted>}
        renderItem={({ item: r }) => (
          <Pressable onPress={() => { setOpen(open === r.id ? null : r.id); setQty(String(Math.max(r.restock_to - r.quantity, 1))); }}
            style={{ backgroundColor: colors.surface, borderRadius: 12, borderWidth: 1, borderColor: colors.line, padding: 12, marginBottom: 8 }}>
            <Row style={{ justifyContent: "space-between" }}>
              <View style={{ flex: 1 }}>
                <Text style={{ fontWeight: "700" }}>{r.name}</Text>
                <Text style={{ color: colors.info, fontSize: 12, fontWeight: "700" }}>📍 Aisle {r.aisle}, Row {r.row}</Text>
              </View>
              <Badge text={`${r.quantity}${r.low ? " · LOW" : ""}`} tone={r.low ? "danger" : "ok"} />
            </Row>
            {open === r.id && (
              <Row style={{ marginTop: 10 }}>
                <Input keyboardType="number-pad" value={qty} onChangeText={setQty} style={{ flex: 1 }} placeholder="Units added" />
                <Button small title="Record restock" onPress={() => restock(r)} />
              </Row>)}
          </Pressable>)} />
    </View>
  );
}
