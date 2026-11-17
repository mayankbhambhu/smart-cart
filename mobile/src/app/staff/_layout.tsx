import { Redirect, Tabs } from "expo-router";
import { LogoutButton, tabIcon } from "@/components/AppChrome";
import { useAuth } from "@/lib/auth";
import { appFor, homeHref } from "@/lib/roles";
import { colors } from "@/lib/theme";

/** Store-operations app: opened for worker, floor manager, store manager and owner accounts. */
export default function StaffLayout() {
  const { user, ready } = useAuth();
  if (!ready) return null;
  if (!user) return <Redirect href="/login" />;
  if (appFor(user.role) !== "staff") return <Redirect href={homeHref(user.role)} />;
  if (user.must_change_password) return <Redirect href="/change-password" />;
  return (
    <Tabs screenOptions={{ tabBarActiveTintColor: colors.brand, headerTitleStyle: { fontWeight: "800" }, headerRight: () => <LogoutButton /> }}>
      <Tabs.Screen name="index" options={{ title: "Overview", tabBarIcon: tabIcon("🏠") }} />
      <Tabs.Screen name="tasks" options={{ title: "Tasks", tabBarIcon: tabIcon("✅") }} />
      <Tabs.Screen name="inventory" options={{ title: "Inventory", tabBarIcon: tabIcon("📦") }} />
      <Tabs.Screen name="orders" options={{ title: "Orders", tabBarIcon: tabIcon("🧾") }} />
      <Tabs.Screen name="more" options={{ title: "More", tabBarIcon: tabIcon("☰") }} />
      <Tabs.Screen name="gate" options={{ title: "Exit gate scanner", href: null }} />
    </Tabs>
  );
}
