import { CameraView, useCameraPermissions } from "expo-camera";
import * as Haptics from "expo-haptics";
import { useEffect, useRef, useState } from "react";
import { Alert, ScrollView, Text, View } from "react-native";
import { Chip } from "@/components/Chip";
import { Button, Card, Input, Muted, Row, s } from "@/components/ui";
import { api, logError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { colors, inr } from "@/lib/theme";

type Gate = { id: number; name: string };
type Result = { open: boolean; reason: string; order_number: string | null; items: number | null; total: number | null };

/** Staff hold the phone up to a shopper's receipt QR: the API verifies payment and opens (or denies) the gate. */
export default function GateScanner() {
  const { user } = useAuth();
  const sid = user!.store_id!;
  const [perm, requestPerm] = useCameraPermissions();
  const [gates, setGates] = useState<Gate[]>([]);
  const [gateId, setGateId] = useState<number | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [manual, setManual] = useState("");
  const busy = useRef(false);

  useEffect(() => {
    api.get<{ gates: Gate[] }>(`/ops/stores/${sid}/gates`).then((r) => { setGates(r.gates); setGateId(r.gates[0]?.id ?? null); }).catch(logError);
  }, [sid]);

  const verify = async (code: string) => {
    if (!gateId || busy.current) return;
    busy.current = true;
    try {
      const r = await api.post<Result>(`/gate/${gateId}/simulate`, { code });
      setResult(r);
      Haptics.notificationAsync(r.open ? Haptics.NotificationFeedbackType.Success : Haptics.NotificationFeedbackType.Error);
    } catch (e) { Alert.alert("Gate", (e as Error).message); busy.current = false; }
  };
  const next = () => { setResult(null); setManual(""); busy.current = false; };

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.pad} keyboardShouldPersistTaps="handled">
      <Row style={{ flexWrap: "wrap" }}>{gates.map((g) => <Chip key={g.id} label={g.name} active={gateId === g.id} onPress={() => setGateId(g.id)} />)}</Row>
      {result ? (
        <Card style={{ alignItems: "center", backgroundColor: result.open ? colors.brandSoft : colors.dangerSoft }}>
          <Text style={{ fontSize: 26, fontWeight: "900", color: result.open ? colors.brand : colors.danger }}>{result.open ? "🟢 GATE OPEN" : "🔴 GATE CLOSED"}</Text>
          <Text style={{ marginTop: 6, textAlign: "center" }}>{result.reason}</Text>
          {result.order_number && <Muted>{result.order_number} · {result.items} items · {inr(result.total)}</Muted>}
          <Button title="Scan next" onPress={next} style={{ marginTop: 12, alignSelf: "stretch" }} />
        </Card>
      ) : perm?.granted ? (
        <View style={{ height: 320, borderRadius: 14, overflow: "hidden", marginBottom: 12 }}>
          <CameraView style={{ flex: 1 }} facing="back" barcodeScannerSettings={{ barcodeTypes: ["qr"] }} onBarcodeScanned={({ data }) => verify(data)} />
        </View>
      ) : (
        <Card><Muted>Allow the camera to scan shoppers' receipt QR codes.</Muted><Button title="Allow camera" onPress={requestPerm} style={{ marginTop: 8 }} /></Card>
      )}
      {!result && (
        <Card>
          <Muted>Or type the code under the receipt QR:</Muted>
          <Row style={{ marginTop: 8 }}><Input value={manual} onChangeText={setManual} placeholder="FF1.123.abcd…" autoCapitalize="none" style={{ flex: 1 }} /><Button small title="Verify" onPress={() => verify(manual.trim())} /></Row>
        </Card>)}
    </ScrollView>
  );
}
