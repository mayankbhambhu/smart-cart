import * as AppleAuthentication from "expo-apple-authentication";
import * as Google from "expo-auth-session/providers/google";
import * as WebBrowser from "expo-web-browser";
import { useEffect, useState } from "react";
import { Alert, KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, View } from "react-native";
import { GoogleButton } from "@/components/GoogleButton";
import { Button, Card, H1, H2, Input, Muted, Row, s } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { API_URL, GOOGLE_IDS, PRIVACY_URL } from "@/lib/config";
import { sendMagicLink } from "@/lib/firebase";
import { completeSignIn, fetchProviders, type Providers, signInWithSso } from "@/lib/signin";
import { colors } from "@/lib/theme";
import type { TokenOut } from "@/lib/types";

WebBrowser.maybeCompleteAuthSession();

export default function Login() {
  const { signIn } = useAuth();
  const [mode, setMode] = useState<"email" | "phone" | "register">("email");
  const [f, setF] = useState({ identifier: "", password: "", full_name: "", phone: "", code: "" });
  const [otpSent, setOtpSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f) => (v: string) => setF({ ...f, [k]: v });
  const [providers, setProviders] = useState<Providers | null>(null);
  const [magicEmail, setMagicEmail] = useState("");
  const [magicSent, setMagicSent] = useState<string | null>(null);
  useEffect(() => { fetchProviders().then(setProviders).catch(() => setProviders(null)); }, []);
  const googleReady = !!providers?.google.enabled && !!(GOOGLE_IDS.web || GOOGLE_IDS.ios || GOOGLE_IDS.android);
  const notSetUp = (what: string, settings: string) =>
    Alert.alert(`${what} isn't set up yet`, `Add ${settings} to the backend settings (see README → Sign-in options).`);

  const [, googleResp, googlePrompt] = Google.useIdTokenAuthRequest({
    iosClientId: GOOGLE_IDS.ios || undefined, androidClientId: GOOGLE_IDS.android || undefined,
    webClientId: GOOGLE_IDS.web || undefined, clientId: GOOGLE_IDS.web || "unset",
  });
  useEffect(() => {
    if (googleResp?.type === "success" && googleResp.params.id_token)
      run(() => api.post<TokenOut>("/auth/google", { id_token: googleResp.params.id_token }));
  }, [googleResp]);

  async function run(fn: () => Promise<TokenOut>) {
    setBusy(true);
    try { await completeSignIn(signIn, await fn()); }  // the account's role decides which app opens
    catch (e) { Alert.alert("Sign in failed", (e as Error).message); }
    finally { setBusy(false); }
  }

  async function sendOtp() {
    setBusy(true);
    try {
      const r = await api.post<{ dev_code?: string }>("/auth/otp/request", { phone: f.phone });
      setOtpSent(true);
      if (r.dev_code) Alert.alert("Development mode", `Your code is ${r.dev_code}`);
    } catch (e) { Alert.alert("OTP", (e as Error).message); }
    finally { setBusy(false); }
  }

  async function emailMeALink() {
    const cfg = providers?.firebase_email_link;
    if (!cfg?.enabled || !cfg.config) return notSetUp("Email sign-in links", "the FIREBASE_* settings");
    if (!/^\S+@\S+\.\S+$/.test(magicEmail.trim())) return Alert.alert("Email link", "Enter your email address.");
    setBusy(true);
    try { await sendMagicLink(cfg.config, cfg.continue_url, magicEmail.trim()); setMagicSent(magicEmail.trim()); }
    catch (e) { Alert.alert("Email link", (e as Error).message); }
    finally { setBusy(false); }
  }

  async function apple() {
    try {
      const cred = await AppleAuthentication.signInAsync({ requestedScopes: [
        AppleAuthentication.AppleAuthenticationScope.FULL_NAME, AppleAuthentication.AppleAuthenticationScope.EMAIL] });
      const name = [cred.fullName?.givenName, cred.fullName?.familyName].filter(Boolean).join(" ");
      await run(() => api.post<TokenOut>("/auth/apple", { id_token: cred.identityToken, full_name: name || undefined }));
    } catch (e) { if ((e as { code?: string }).code !== "ERR_REQUEST_CANCELED") Alert.alert("Apple", (e as Error).message); }
  }

  return (
    <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={s.screen}>
      <ScrollView contentContainerStyle={[s.pad, { paddingTop: 80 }]} keyboardShouldPersistTaps="handled">
        <View style={{ alignItems: "center", marginBottom: 24 }}>
          <View style={{ width: 64, height: 64, borderRadius: 18, backgroundColor: colors.brand, alignItems: "center", justifyContent: "center" }}>
            <Text style={{ color: "#fff", fontSize: 32, fontWeight: "900" }}>F</Text></View>
          <H1>FreshFlow</H1><Muted>Groceries in minutes · Scan & Go in store</Muted>
        </View>
        <Card>
          <Row style={{ marginBottom: 12 }}>
            {(["email", "phone", "register"] as const).map((m) => (
              <Button key={m} small title={{ email: "Email", phone: "Phone OTP", register: "Sign up" }[m]}
                variant={mode === m ? "primary" : "secondary"} onPress={() => setMode(m)} style={{ flex: 1 }} />))}
          </Row>
          {mode === "email" && <View style={{ gap: 10 }}>
            <Input placeholder="Email or phone" autoCapitalize="none" keyboardType="email-address" value={f.identifier} onChangeText={set("identifier")} />
            <Input placeholder="Password" secureTextEntry value={f.password} onChangeText={set("password")} />
            <Button title="Sign in" loading={busy} onPress={() => run(() => api.post("/auth/login", { identifier: f.identifier, password: f.password }))} />
          </View>}
          {mode === "phone" && <View style={{ gap: 10 }}>
            <Input placeholder="+91 98xxxxxxxx" keyboardType="phone-pad" value={f.phone} onChangeText={set("phone")} />
            {otpSent ? <>
              <Input placeholder="6-digit code" keyboardType="number-pad" maxLength={6} value={f.code} onChangeText={set("code")} />
              <Input placeholder="Your name (new accounts)" value={f.full_name} onChangeText={set("full_name")} />
              <Button title="Verify & continue" loading={busy} onPress={() => run(() => api.post("/auth/otp/verify", { phone: f.phone, code: f.code, full_name: f.full_name }))} />
            </> : <Button title="Send OTP" loading={busy} onPress={sendOtp} />}
          </View>}
          {mode === "register" && <View style={{ gap: 10 }}>
            <Input placeholder="Full name" value={f.full_name} onChangeText={set("full_name")} />
            <Input placeholder="Email" autoCapitalize="none" keyboardType="email-address" value={f.identifier} onChangeText={set("identifier")} />
            <Input placeholder="Password (min 8)" secureTextEntry value={f.password} onChangeText={set("password")} />
            <Button title="Create account" loading={busy} onPress={() => run(() => api.post("/auth/register", { full_name: f.full_name, email: f.identifier, password: f.password }))} />
          </View>}
        </Card>
        <View style={{ gap: 10, marginBottom: 10 }}>
          <GoogleButton disabled={!googleReady} onPress={() => (googleReady ? googlePrompt() : notSetUp("Google sign-in", "GOOGLE_WEB_CLIENT_ID and the app's Google client IDs"))} />
          <Button variant="secondary" title={providers?.sso.enabled ? `🔐 ${providers.sso.label}` : "🔐 Sign in with SSO"}
            onPress={() => (providers?.sso.enabled ? run(signInWithSso) : notSetUp("Single sign-on", "the OIDC_* settings"))} />
        </View>
        <Card>
          <H2>✉️ Email me a sign-in link</H2>
          {magicSent ? <>
            <Muted>We sent a link to {magicSent}. Open it on this phone to sign in. No password needed.</Muted>
            <Button small variant="ghost" title="Use a different email" onPress={() => setMagicSent(null)} />
          </> : <>
            <Input placeholder="you@example.com" autoCapitalize="none" keyboardType="email-address" value={magicEmail} onChangeText={setMagicEmail} />
            <Button title="Send link" variant="secondary" loading={busy} style={{ marginTop: 8 }} onPress={emailMeALink}
              disabled={!providers?.firebase_email_link.enabled} />
          </>}
        </Card>
        {Platform.OS === "ios" && <AppleAuthentication.AppleAuthenticationButton
          buttonType={AppleAuthentication.AppleAuthenticationButtonType.SIGN_IN} buttonStyle={AppleAuthentication.AppleAuthenticationButtonStyle.BLACK}
          cornerRadius={12} style={{ height: 48 }} onPress={apple} />}
        <Pressable onPress={() => WebBrowser.openBrowserAsync(PRIVACY_URL)}>
          <Muted>By continuing you agree to our <Text style={{ textDecorationLine: "underline" }}>privacy policy</Text>.</Muted>
        </Pressable>
        {__DEV__ && <Muted>Server: {API_URL}</Muted>}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}
