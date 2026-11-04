import { CameraView, useCameraPermissions } from "expo-camera";
import * as Haptics from "expo-haptics";
import { router } from "expo-router";
import { useRef, useState } from "react";
import { Alert, Text, View } from "react-native";
import { Button, Muted, s } from "@/components/ui";
import { api } from "@/lib/api";
import { useCart } from "@/lib/cart";
import { inr } from "@/lib/theme";
import type { Cart } from "@/lib/types";

/** Scan a product barcode straight into the smart cart. */
export default function Scan() {
  const [perm, requestPerm] = useCameraPermissions();
  const { replace } = useCart();
  const [last, setLast] = useState<string | null>(null);
  const busy = useRef(false);

  if (!perm) return <View style={s.screen} />;
  if (!perm.granted) return (
    <View style={[s.screen, s.pad, { justifyContent: "center", gap: 12 }]}>
      <Muted>We need the camera to scan product barcodes.</Muted>
      <Button title="Allow camera" onPress={requestPerm} />
    </View>);

  return (
    <View style={{ flex: 1, backgroundColor: "#000" }}>
      <CameraView style={{ flex: 1 }} facing="back"
        barcodeScannerSettings={{ barcodeTypes: ["ean13", "ean8", "upc_a", "upc_e", "code128", "qr"] }}
        onBarcodeScanned={async ({ data }) => {
          if (busy.current || data === last) return;
          busy.current = true;
          try {
            const cart = await api.post<Cart>("/cart/items", { barcode: data, quantity: 1 });
            replace(cart);
            setLast(data);
            Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
            const added = cart.items[cart.items.length - 1];
            Alert.alert("Added to cart", `${added?.name ?? data}\nCart total ${inr(cart.total)}`, [
              { text: "Scan next", onPress: () => { busy.current = false; setLast(null); } },
              { text: "Done", onPress: () => router.back() }]);
          } catch (e) {
            Alert.alert("Not recognised", (e as Error).message, [{ text: "OK", onPress: () => { busy.current = false; } }]);
          }
        }} />
      <View style={{ position: "absolute", bottom: 40, left: 20, right: 20 }}>
        <Text style={{ color: "#fff", textAlign: "center", marginBottom: 12 }}>Point at the product barcode</Text>
        <Button title="Close" variant="secondary" onPress={() => router.back()} />
      </View>
    </View>
  );
}
