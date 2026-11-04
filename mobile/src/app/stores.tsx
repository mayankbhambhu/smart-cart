import * as Location from "expo-location";
import { useEffect, useState } from "react";
import { Linking, ScrollView, Text } from "react-native";
import { Badge, Button, Card, H2, Input, Muted, Row, s } from "@/components/ui";
import { api } from "@/lib/api";
import { useCart } from "@/lib/cart";
import { inr } from "@/lib/theme";
import type { Store } from "@/lib/types";

type StockRow = { store_id: number; store_name: string; product: string; quantity: number; in_stock: boolean; location: string; price: number; distance_km: number | null };

/** Store locator + "is it in stock before I leave home?" */
export default function Stores() {
  const { setup } = useCart();
  const [coords, setCoords] = useState<{ lat: number; lng: number } | null>(null);
  const [stores, setStores] = useState<Store[]>([]);
  const [q, setQ] = useState("");
  const [stock, setStock] = useState<StockRow[] | null>(null);

  useEffect(() => { (async () => {
    const { status } = await Location.requestForegroundPermissionsAsync();
    if (status === "granted") {
      const p = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
      setCoords({ lat: p.coords.latitude, lng: p.coords.longitude });
    }
  })(); }, []);
  useEffect(() => { api.get<Store[]>("/stores", coords ?? {}).then(setStores); }, [coords]);

  const check = async () => { if (q.trim()) setStock(await api.get<StockRow[]>("/stock-check", { q, ...(coords ?? {}) })); };

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.pad}>
      <Card>
        <H2>Check stock</H2>
        <Row><Input placeholder="e.g. Paneer" value={q} onChangeText={setQ} onSubmitEditing={check} style={{ flex: 1 }} /><Button small title="Check" onPress={check} /></Row>
        {stock?.map((r, i) => (
          <Row key={i} style={{ justifyContent: "space-between", paddingVertical: 8 }}>
            <Text style={{ flex: 1 }}>{r.store_name}{"\n"}<Text style={{ fontSize: 12 }}>{r.product} · {r.location} · {inr(r.price)}</Text></Text>
            <Badge text={r.in_stock ? `${r.quantity} in stock` : "Out"} tone={r.in_stock ? "ok" : "danger"} />
          </Row>))}
        {stock && !stock.length && <Muted>Not found in any store.</Muted>}
      </Card>
      {stores.map((st) => (
        <Card key={st.id}>
          <H2>{st.name}</H2>
          <Muted>{st.address}, {st.city}{st.distance_km != null ? ` · ${st.distance_km} km` : ""}</Muted>
          <Muted>Open {st.opens_at}:00 – {st.closes_at}:00</Muted>
          <Row style={{ marginTop: 8 }}>
            <Button small variant="secondary" title="Directions" onPress={() => Linking.openURL(`https://www.google.com/maps/dir/?api=1&destination=${st.latitude},${st.longitude}`)} />
            <Button small title="Order for pickup" onPress={() => setup(st.id, "pickup")} />
          </Row>
        </Card>))}
    </ScrollView>
  );
}
