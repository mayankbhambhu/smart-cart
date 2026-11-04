import { router } from "expo-router";
import { useEffect, useState } from "react";
import { Alert, Platform, Pressable, ScrollView, Text } from "react-native";
import { Badge, Button, Card, H2, Input, Muted, Row, s, SummaryLine } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useCart } from "@/lib/cart";
import { pay } from "@/lib/payments";
import { colors, inr } from "@/lib/theme";
import type { Cart, Order, PaymentIntent } from "@/lib/types";

type Slot = { start: string; label: string; available: number };
const METHODS = [
  { id: "upi", label: "⚡ UPI (GPay · PhonePe · Paytm)" },
  Platform.OS === "ios" ? { id: "apple_pay", label: " Apple Pay" } : { id: "google_pay", label: "G Google Pay" },
  { id: "card", label: "💳 Card" },
  { id: "paypal", label: "🅿️ PayPal" },
];

/** One-tap checkout for delivery, pickup and in-store Scan & Go. */
export default function CartScreen() {
  const { user } = useAuth();
  const { cart, setQty, replace, refresh } = useCart();
  const [method, setMethod] = useState(METHODS[0].id);
  const [address, setAddress] = useState(user?.default_address ?? "");
  const [slots, setSlots] = useState<Slot[]>([]);
  const [slot, setSlot] = useState<string | null>(null);
  const [code, setCode] = useState(cart?.offer_code ?? "");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (cart?.mode === "pickup") api.get<Slot[]>(`/stores/${cart.store_id}/pickup-slots`).then((s) => { setSlots(s); setSlot(s.find((x) => x.available)?.start ?? null); });
  }, [cart?.mode, cart?.store_id]);

  if (!cart) return null;
  const applyOffer = async () => {
    const c = await api.post<Cart>("/cart/offer", { code: code || null });
    replace(c);
    if (c.offer_message) Alert.alert("Offer", c.offer_message);
  };

  const checkout = async () => {
    setBusy(true);
    try {
      const r = await api.post<{ order: Order; payment: PaymentIntent }>("/checkout", {
        payment_method: method, delivery_address: cart.mode === "delivery" ? address : null, pickup_slot: cart.mode === "pickup" ? slot : null });
      const order = await pay(r.payment);
      await refresh();
      router.replace(`/order/${order.id}`);
    } catch (e) { Alert.alert("Payment", (e as Error).message); }
    finally { setBusy(false); }
  };

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.pad}>
      <Card>
        <Row style={{ justifyContent: "space-between" }}><H2>{cart.store_name}</H2><Badge text={{ delivery: "🚴 Delivery", pickup: "🏬 Pickup", instore: "📱 In store" }[cart.mode]} tone="ok" /></Row>
        {cart.items.map((i) => (
          <Row key={i.product_id} style={{ paddingVertical: 8, borderBottomWidth: 1, borderColor: colors.line }}>
            <Text style={{ flex: 1 }}>{i.name}{"\n"}<Text style={{ color: colors.muted, fontSize: 12 }}>{i.unit}{i.location ? ` · 📍 ${i.location}` : ""}</Text></Text>
            <Row style={{ backgroundColor: colors.brand, borderRadius: 8, gap: 0 }}>
              <Pressable onPress={() => setQty(i.product_id, i.quantity - 1)} style={{ padding: 6 }}><Text style={{ color: "#fff", fontWeight: "800" }}> − </Text></Pressable>
              <Text style={{ color: "#fff", fontWeight: "800" }}>{i.quantity}</Text>
              <Pressable onPress={() => setQty(i.product_id, i.quantity + 1)} style={{ padding: 6 }}><Text style={{ color: "#fff", fontWeight: "800" }}> + </Text></Pressable>
            </Row>
            <Text style={{ width: 70, textAlign: "right", fontWeight: "700" }}>{inr(i.line_total)}</Text>
          </Row>))}
        {!cart.items.length && <Muted>Your cart is empty.</Muted>}
      </Card>
      <Card>
        <Row><Input placeholder="Offer code e.g. WELCOME50" autoCapitalize="characters" value={code} onChangeText={setCode} style={{ flex: 1 }} /><Button small title="Apply" variant="secondary" onPress={applyOffer} /></Row>
        <SummaryLine label="Item total" value={inr(cart.subtotal)} />
        {cart.discount > 0 && <SummaryLine label="Discount" value={`−${inr(cart.discount)}`} />}
        {cart.mode === "delivery" && <SummaryLine label="Delivery" value={cart.delivery_fee ? inr(cart.delivery_fee) : "FREE"} />}
        <SummaryLine label="GST" value={inr(cart.tax)} />
        <SummaryLine label="To pay" value={inr(cart.total)} bold />
      </Card>
      {cart.mode === "delivery" && <Card><H2>Deliver to</H2><Input multiline value={address} onChangeText={setAddress} placeholder="Flat, building, street, area" /></Card>}
      {cart.mode === "pickup" && (
        <Card><H2>Pickup slot (today)</H2>
          <Row style={{ flexWrap: "wrap" }}>{slots.map((sl) => (
            <Button key={sl.start} small title={`${sl.label} (${sl.available})`} disabled={!sl.available} variant={slot === sl.start ? "primary" : "secondary"} onPress={() => setSlot(sl.start)} />))}</Row>
          {!slots.length && <Muted>No slots left today.</Muted>}
        </Card>)}
      <Card>
        <H2>Pay with</H2>
        {METHODS.map((m) => <Button key={m.id} title={m.label} variant={method === m.id ? "primary" : "secondary"} onPress={() => setMethod(m.id)} style={{ marginBottom: 6 }} />)}
      </Card>
      <Button title={`Pay ${inr(cart.total)}`} loading={busy} disabled={!cart.items.length} onPress={checkout} />
      {cart.mode === "instore" && <Muted>After paying you get a receipt QR. Scan it at the exit gate and walk out.</Muted>}
    </ScrollView>
  );
}
