import { StripeProvider } from "@stripe/stripe-react-native";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { AuthProvider } from "@/lib/auth";
import { CartProvider } from "@/lib/cart";
import { STRIPE_KEY } from "@/lib/config";
import { colors } from "@/lib/theme";

export default function RootLayout() {
  return (
    <StripeProvider publishableKey={STRIPE_KEY} merchantIdentifier="merchant.app.freshflow" urlScheme="freshflow">
      <AuthProvider>
        <CartProvider>
          <StatusBar style="dark" />
          <Stack screenOptions={{ headerTintColor: colors.brand, contentStyle: { backgroundColor: colors.bg } }}>
            <Stack.Screen name="index" options={{ headerShown: false }} />
            <Stack.Screen name="login" options={{ headerShown: false }} />
            <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
            <Stack.Screen name="cart" options={{ title: "Cart & checkout", presentation: "modal" }} />
            <Stack.Screen name="scan" options={{ title: "Scan barcode", presentation: "fullScreenModal" }} />
            <Stack.Screen name="stores" options={{ title: "Stores & stock check" }} />
            <Stack.Screen name="list/[id]" options={{ title: "Shared list" }} />
            <Stack.Screen name="order/[id]" options={{ title: "Order & receipt" }} />
          </Stack>
        </CartProvider>
      </AuthProvider>
    </StripeProvider>
  );
}
