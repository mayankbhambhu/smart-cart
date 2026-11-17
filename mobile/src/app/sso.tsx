import { router, useGlobalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, ScrollView } from "react-native";
import { Button, Card, H2, Muted, s } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { completeSignIn } from "@/lib/signin";
import { colors } from "@/lib/theme";
import type { TokenOut } from "@/lib/types";

/** Fallback landing for single sign-on when the phone reopens the app directly with the one-time code. */
export default function SsoReturn() {
  const { code, error } = useGlobalSearchParams<{ code?: string; error?: string }>();
  const { signIn } = useAuth();
  const [message, setMessage] = useState(error ? String(error) : "Signing you in…");
  useEffect(() => {
    if (!code || error) return;
    api.post<TokenOut>("/auth/exchange", { code: String(code) })
      .then((p) => completeSignIn(signIn, p))
      .catch((e) => setMessage((e as Error).message));
  }, [code, error]);
  return (
    <ScrollView style={s.screen} contentContainerStyle={s.pad}>
      <Card>
        <H2>Single sign-on</H2>
        {!error && <ActivityIndicator color={colors.brand} style={{ marginVertical: 12 }} />}
        <Muted>{message}</Muted>
        <Button variant="secondary" title="Back to sign in" style={{ marginTop: 12 }} onPress={() => router.replace("/login")} />
      </Card>
    </ScrollView>
  );
}
