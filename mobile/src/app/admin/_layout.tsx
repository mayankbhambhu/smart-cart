import { Redirect, Tabs } from "expo-router";
import { LogoutButton, tabIcon } from "@/components/AppChrome";
import { useAuth } from "@/lib/auth";
import { appFor, homeHref } from "@/lib/roles";
import { colors } from "@/lib/theme";

/** Admin app: opened only for platform admin accounts. */
export default function AdminLayout() {
  const { user, ready } = useAuth();
  if (!ready) return null;
  if (!user) return <Redirect href="/login" />;
  if (appFor(user.role) !== "admin") return <Redirect href={homeHref(user.role)} />;
  return (
    <Tabs screenOptions={{ tabBarActiveTintColor: colors.brand, headerTitleStyle: { fontWeight: "800" }, headerRight: () => <LogoutButton /> }}>
      <Tabs.Screen name="index" options={{ title: "Overview", tabBarIcon: tabIcon("📊") }} />
      <Tabs.Screen name="requests" options={{ title: "Requests", tabBarIcon: tabIcon("🔐") }} />
      <Tabs.Screen name="stores" options={{ title: "Stores", tabBarIcon: tabIcon("🏬") }} />
      <Tabs.Screen name="employees" options={{ title: "Employees", tabBarIcon: tabIcon("👥") }} />
      <Tabs.Screen name="issues" options={{ title: "Issues", tabBarIcon: tabIcon("🛟") }} />
    </Tabs>
  );
}
