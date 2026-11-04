import { router, useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { Alert, Pressable, ScrollView, Text } from "react-native";
import { Badge, Button, Card, H2, Input, Muted, Row, s } from "@/components/ui";
import { api } from "@/lib/api";
import type { ListSummary, ShoppingList } from "@/lib/types";

export default function Lists() {
  const [lists, setLists] = useState<ListSummary[]>([]);
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const load = useCallback(() => { api.get<ListSummary[]>("/lists").then(setLists); }, []);
  useFocusEffect(load);

  const create = async () => {
    if (!name.trim()) return;
    const l = await api.post<ShoppingList>("/lists", { name });
    setName(""); router.push(`/list/${l.id}`);
  };
  const join = async () => {
    try { const l = await api.post<ShoppingList>(`/lists/join/${code.trim()}`); setCode(""); router.push(`/list/${l.id}`); }
    catch (e) { Alert.alert("Join list", (e as Error).message); }
  };

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.pad}>
      {lists.map((l) => (
        <Pressable key={l.id} onPress={() => router.push(`/list/${l.id}`)}>
          <Card>
            <H2>📝 {l.name}</H2>
            <Muted>{l.open_count} to buy · {l.item_count} items · {l.member_count} member{l.member_count > 1 ? "s" : ""}</Muted>
            <Badge text={`Invite code ${l.invite_code}`} />
          </Card>
        </Pressable>))}
      {!lists.length && <Muted>No lists yet. Create one and share the invite code with your family.</Muted>}
      <Card>
        <H2>New list</H2>
        <Row><Input placeholder="e.g. Weekly groceries" value={name} onChangeText={setName} style={{ flex: 1 }} /><Button small title="Create" onPress={create} /></Row>
        <Text style={{ height: 12 }} />
        <H2>Join a family list</H2>
        <Row><Input placeholder="Invite code" autoCapitalize="characters" value={code} onChangeText={setCode} style={{ flex: 1 }} /><Button small title="Join" variant="secondary" onPress={join} /></Row>
      </Card>
    </ScrollView>
  );
}
