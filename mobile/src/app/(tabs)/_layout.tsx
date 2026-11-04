import { Redirect, Tabs } from "expo-router";
import { Text } from "react-native";
import { useAuth } from "@/lib/auth";
import { colors } from "@/lib/theme";

const icon = (e: string) => ({ focused }: { focused: boolean }) => <Text style={{ fontSize: 20, opacity: focused ? 1 : 0.55 }}>{e}</Text>;

export default function TabsLayout() {
  const { user, ready } = useAuth();
  if (ready && !user) return <Redirect href="/login" />;
  return (
    <Tabs screenOptions={{ tabBarActiveTintColor: colors.brand, headerTitleStyle: { fontWeight: "800" } }}>
      <Tabs.Screen name="index" options={{ title: "Shop", tabBarIcon: icon("🛍️") }} />
      <Tabs.Screen name="instore" options={{ title: "Scan & Go", tabBarIcon: icon("📱") }} />
      <Tabs.Screen name="lists" options={{ title: "Family lists", tabBarIcon: icon("📝") }} />
      <Tabs.Screen name="orders" options={{ title: "Orders", tabBarIcon: icon("🧾") }} />
      <Tabs.Screen name="profile" options={{ title: "Profile", tabBarIcon: icon("👤") }} />
    </Tabs>
  );
}
