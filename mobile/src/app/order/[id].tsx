import { useLocalSearchParams } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { Alert, ScrollView, Text, View } from "react-native";
import { QRCode } from "@/components/QRCode";
import { Badge, Button, Card, H2, Muted, s, SummaryLine } from "@/components/ui";
import { api } from "@/lib/api";
import { colors, inr, nice, when } from "@/lib/theme";
import type { Order } from "@/lib/types";

/** Order details + the digital receipt barcode scanned at the exit gate. */
export default function OrderDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [o, setO] = useState<Order | null>(null);
  const load = useCallback(() => { api.get<Order>(`/orders/${id}`).then(setO); }, [id]);
  useEffect(() => { load(); const t = setInterval(load, 5000); return () => clearInterval(t); }, [load]);
  if (!o) return null;
  const showReceipt = o.receipt_code && o.fulfilment !== "delivery";

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.pad}>
      {showReceipt && (
        <Card style={{ alignItems: "center" }}>
          {o.exit_verified_at ? (
            <View style={{ backgroundColor: colors.brandSoft, padding: 24, borderRadius: 14, alignItems: "center" }}>
              <Text style={{ fontSize: 22, fontWeight: "900", color: colors.brand }}>✓ Verified at exit</Text>
              <Muted>{when(o.exit_verified_at)} · have a nice day!</Muted>
            </View>
          ) : (<>
            <H2>Scan at the exit gate</H2>
            <QRCode value={o.receipt_code!} size={250} />
            <Muted>{o.number} · {inr(o.total)} paid</Muted>
          </>)}
        </Card>)}
      <Card>
        <H2>{o.number}</H2>
        <Badge text={nice(o.status)} tone={o.status === "cancelled" ? "danger" : "ok"} />
        <Muted>{o.store_name} · {nice(o.fulfilment)} · paid {when(o.paid_at)} via {nice(o.payment_method)}</Muted>
        {o.pickup_slot && <Text style={{ marginTop: 6 }}>🏬 Pickup at {when(o.pickup_slot)}</Text>}
        <View style={{ height: 8 }} />
        {o.items.map((i, k) => <SummaryLine key={k} label={`${i.quantity}× ${i.name}`} value={inr(i.line_total)} />)}
        {o.discount > 0 && <SummaryLine label="Discount" value={`−${inr(o.discount)}`} />}
        {o.delivery_fee > 0 && <SummaryLine label="Delivery" value={inr(o.delivery_fee)} />}
        <SummaryLine label="GST" value={inr(o.tax)} />
        <SummaryLine label="Total" value={inr(o.total)} bold />
      </Card>
      {o.status === "preparing" && <Button variant="danger" title="Cancel order" onPress={async () => {
        try { setO(await api.post<Order>(`/orders/${o.id}/cancel`)); } catch (e) { Alert.alert("Cancel", (e as Error).message); } }} />}
    </ScrollView>
  );
}
