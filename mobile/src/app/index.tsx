import { Redirect } from "expo-router";
import { ActivityIndicator, View } from "react-native";
import { useAuth } from "@/lib/auth";
import { homeHref } from "@/lib/roles";
import { colors } from "@/lib/theme";

/** Entry point: the signed-in account's role decides which app opens. */
export default function Index() {
  const { user, ready } = useAuth();
  if (!ready) return <View style={{ flex: 1, justifyContent: "center" }}><ActivityIndicator color={colors.brand} /></View>;
  if (!user) return <Redirect href="/login" />;
  if (user.must_change_password) return <Redirect href="/change-password" />;
  return <Redirect href={homeHref(user.role)} />;
}
