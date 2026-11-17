import { router } from "expo-router";
import { useState } from "react";
import { Alert, ScrollView } from "react-native";
import { Button, Card, H2, Input, Muted, s } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { homeHref } from "@/lib/roles";

/** Staff get a temporary password from the admin team; they must replace it before using the app. */
export default function ChangePassword() {
  const { user, refresh } = useAuth();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [busy, setBusy] = useState(false);
  const save = async () => {
    if (next.length < 8) return Alert.alert("Password", "Use at least 8 characters.");
    setBusy(true);
    try {
      await api.post("/me/password", { current_password: current, new_password: next });
      await refresh();
      router.replace(homeHref(user?.role));
    } catch (e) { Alert.alert("Password", (e as Error).message); }
    finally { setBusy(false); }
  };
  return (
    <ScrollView style={s.screen} contentContainerStyle={s.pad} keyboardShouldPersistTaps="handled">
      <Card>
        <H2>Set your own password</H2>
        {user?.must_change_password && <Muted>You signed in with a temporary password from the admin team. Choose your own to continue.</Muted>}
        <Input placeholder="Current (temporary) password" secureTextEntry value={current} onChangeText={setCurrent} style={{ marginTop: 10 }} />
        <Input placeholder="New password (min 8)" secureTextEntry value={next} onChangeText={setNext} style={{ marginTop: 10 }} />
        <Button title="Save password" loading={busy} onPress={save} style={{ marginTop: 12 }} />
      </Card>
    </ScrollView>
  );
}
