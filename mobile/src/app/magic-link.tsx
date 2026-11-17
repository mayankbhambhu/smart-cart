import { useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, ScrollView } from "react-native";
import { Button, Card, H2, Input, Muted, s } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { finishMagicLink, NeedEmailError } from "@/lib/firebase";
import { completeSignIn, fetchProviders } from "@/lib/signin";
import { colors } from "@/lib/theme";
import type { TokenOut } from "@/lib/types";

/** Opened from the emailed sign-in link (via our web page, which forwards the link here). */
export default function MagicLink() {
  const { link } = useLocalSearchParams<{ link?: string }>();
  const { signIn } = useAuth();
  const [state, setState] = useState<"working" | "need-email" | "error">("working");
  const [message, setMessage] = useState("Signing you in…");
  const [email, setEmail] = useState("");

  const finish = async (address?: string) => {
    setState("working");
    try {
      if (!link) throw new Error("The sign-in link is missing. Request a new one.");
      const p = await fetchProviders();
      if (!p.firebase_email_link.config) throw new Error("Email-link sign-in is not set up on the server.");
      const idToken = await finishMagicLink(p.firebase_email_link.config, String(link), address);
      await completeSignIn(signIn, await api.post<TokenOut>("/auth/firebase", { id_token: idToken }));
    } catch (e) {
      if (e instanceof NeedEmailError) { setState("need-email"); setMessage(e.message); }
      else { setState("error"); setMessage((e as Error).message); }
    }
  };
  useEffect(() => { finish(); }, [link]);

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.pad} keyboardShouldPersistTaps="handled">
      <Card>
        <H2>Email sign-in link</H2>
        {state === "working" && <ActivityIndicator color={colors.brand} style={{ marginVertical: 12 }} />}
        <Muted>{message}</Muted>
        {state === "need-email" && <>
          <Input placeholder="you@example.com" autoCapitalize="none" keyboardType="email-address" value={email} onChangeText={setEmail} style={{ marginTop: 10 }} />
          <Button title="Continue" style={{ marginTop: 10 }} onPress={() => finish(email.trim())} />
        </>}
      </Card>
    </ScrollView>
  );
}
