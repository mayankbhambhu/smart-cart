import { router, useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { Alert, Pressable, ScrollView, Text } from "react-native";
import { Button, Card, H2, Input, Muted, Row, s } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { colors } from "@/lib/theme";
import type { User } from "@/lib/types";

const DIETS = ["vegan", "vegetarian", "gluten_free", "dairy_free", "organic", "sugar_free"];
type Method = { id: number; kind: string; label: string; is_default: boolean };

export default function Profile() {
  const { user, refresh, signOut } = useAuth();
  const [form, setForm] = useState({ full_name: user?.full_name ?? "", phone: user?.phone ?? "", default_address: user?.default_address ?? "" });
  const [diets, setDiets] = useState<string[]>(user?.dietary_preferences ?? []);
  const [methods, setMethods] = useState<Method[]>([]);
  const [newMethod, setNewMethod] = useState({ kind: "upi", label: "" });
  const loadMethods = useCallback(() => { api.get<Method[]>("/me/payment-methods").then(setMethods); }, []);
  useFocusEffect(loadMethods);

  const save = async () => {
    try { await api.patch<User>("/me", { ...form, phone: form.phone || null, dietary_preferences: diets }); await refresh(); Alert.alert("Saved", "Profile updated"); }
    catch (e) { Alert.alert("Error", (e as Error).message); }
  };
  const addMethod = async () => {
    if (!newMethod.label) return;
    await api.post("/me/payment-methods", newMethod); setNewMethod({ ...newMethod, label: "" }); loadMethods();
  };

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.pad}>
      <Card>
        <H2>Personal details</H2>
        <Muted>{user?.email ?? user?.phone}</Muted>
        <Input placeholder="Full name" value={form.full_name} onChangeText={(v) => setForm({ ...form, full_name: v })} style={{ marginTop: 8 }} />
        <Input placeholder="Phone" value={form.phone} onChangeText={(v) => setForm({ ...form, phone: v })} style={{ marginTop: 8 }} />
        <Input placeholder="Default delivery address" multiline value={form.default_address} onChangeText={(v) => setForm({ ...form, default_address: v })} style={{ marginTop: 8 }} />
        <Text style={{ fontWeight: "700", marginTop: 12, marginBottom: 6 }}>Dietary preferences</Text>
        <Row style={{ flexWrap: "wrap" }}>
          {DIETS.map((d) => { const on = diets.includes(d); return (
            <Pressable key={d} onPress={() => setDiets(on ? diets.filter((x) => x !== d) : [...diets, d])}
              style={{ paddingHorizontal: 12, paddingVertical: 6, borderRadius: 999, borderWidth: 1, borderColor: on ? colors.brand : colors.line, backgroundColor: on ? colors.brand : "#fff" }}>
              <Text style={{ color: on ? "#fff" : colors.ink2, fontWeight: "600" }}>{d.replace("_", " ")}</Text></Pressable>); })}
        </Row>
        <Button title="Save profile" onPress={save} style={{ marginTop: 12 }} />
      </Card>
      <Card>
        <H2>Payment methods</H2>
        {methods.map((m) => (
          <Row key={m.id} style={{ justifyContent: "space-between", paddingVertical: 6 }}>
            <Text>{m.label} {m.is_default ? "· default" : ""}</Text>
            <Button small variant="ghost" title="Remove" onPress={async () => { await api.del(`/me/payment-methods/${m.id}`); loadMethods(); }} />
          </Row>))}
        <Row style={{ flexWrap: "wrap", marginTop: 6 }}>
          {["upi", "card", "apple_pay", "google_pay", "paypal"].map((k) => (
            <Button key={k} small title={k.replace("_", " ")} variant={newMethod.kind === k ? "primary" : "secondary"} onPress={() => setNewMethod({ ...newMethod, kind: k })} />))}
        </Row>
        <Row style={{ marginTop: 8 }}><Input placeholder="name@okbank / Visa •••• 4242" value={newMethod.label} onChangeText={(v) => setNewMethod({ ...newMethod, label: v })} style={{ flex: 1 }} /><Button small title="Add" onPress={addMethod} /></Row>
        <Muted>Cards are tokenised by Stripe; card numbers never touch our servers.</Muted>
      </Card>
      <Button title="Purchase history" variant="secondary" onPress={() => router.push("/(tabs)/orders")} style={{ marginBottom: 10 }} />
      <Button title="Log out" variant="danger" onPress={async () => { await signOut(); router.replace("/login"); }} />
    </ScrollView>
  );
}
