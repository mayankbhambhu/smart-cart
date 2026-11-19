import { Pressable, StyleSheet, Text, View } from "react-native";
import { CATEGORY_ICON, colors, inr } from "@/lib/theme";
import type { Product } from "@/lib/types";
import { Badge } from "./ui";

export function ProductCard({ p, qty, onChange }: { p: Product; qty: number; onChange: (q: number) => void }) {
  return (
    <View style={st.card}>
      <View style={st.img}><Text style={{ fontSize: 34 }}>{CATEGORY_ICON[p.category_id] ?? "🛒"}</Text></View>
      <Text numberOfLines={2} style={st.name}>{p.name}</Text>
      <Text style={st.unit}>{p.brand} · {p.unit}</Text>
      <Text style={st.loc}>📍 {p.location}</Text>
      {!p.in_stock ? <Badge text="Out of stock" tone="danger" /> : p.quantity < 10 ? <Badge text={`Only ${p.quantity} left`} tone="warn" /> : null}
      <View style={st.foot}>
        <View><Text style={st.price}>{inr(p.price)}</Text>{p.mrp > p.price && <Text style={st.mrp}>{inr(p.mrp)}</Text>}</View>
        {qty > 0 ? (
          <View style={st.qty}>
            <Pressable onPress={() => onChange(qty - 1)} style={st.qBtn}><Text style={st.qTxt}>−</Text></Pressable>
            <Text style={st.qNum}>{qty}</Text>
            <Pressable onPress={() => onChange(qty + 1)} style={st.qBtn}><Text style={st.qTxt}>+</Text></Pressable>
          </View>
        ) : (
          <Pressable disabled={!p.in_stock} onPress={() => onChange(1)} style={[st.add, !p.in_stock && { opacity: 0.4 }]}>
            <Text style={{ color: colors.brand, fontWeight: "800" }}>ADD</Text></Pressable>
        )}
      </View>
    </View>
  );
}

const st = StyleSheet.create({
  card: { flex: 1, backgroundColor: colors.surface, borderRadius: 14, borderWidth: 1, borderColor: colors.line, padding: 10, gap: 4, margin: 5 },
  img: { height: 86, borderRadius: 10, backgroundColor: colors.surface2, alignItems: "center", justifyContent: "center" },
  name: { fontWeight: "700", fontSize: 14, color: colors.ink, minHeight: 36 },
  unit: { color: colors.muted, fontSize: 12 },
  loc: { color: colors.info, fontSize: 12, fontWeight: "700" },
  foot: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginTop: 6 },
  price: { fontWeight: "800", fontSize: 15, color: colors.ink },
  mrp: { textDecorationLine: "line-through", color: colors.muted, fontSize: 11 },
  add: { borderWidth: 1, borderColor: colors.brand, borderRadius: 9, paddingHorizontal: 14, paddingVertical: 6, backgroundColor: colors.brandSoft },
  qty: { flexDirection: "row", alignItems: "center", backgroundColor: colors.brand, borderRadius: 9 },
  qBtn: { paddingHorizontal: 10, paddingVertical: 5 }, qTxt: { color: "#fff", fontWeight: "800", fontSize: 16 },
  qNum: { color: "#fff", fontWeight: "800", minWidth: 16, textAlign: "center" },
});
