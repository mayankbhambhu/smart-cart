import { router } from "expo-router";
import { Alert, Pressable, Text } from "react-native";
import { useAuth } from "@/lib/auth";
import { colors } from "@/lib/theme";

export const tabIcon = (e: string) => ({ focused }: { focused: boolean }) =>
  <Text style={{ fontSize: 20, opacity: focused ? 1 : 0.55 }}>{e}</Text>;

/** Header button to sign out, used by the staff and admin apps. */
export function LogoutButton() {
  const { signOut } = useAuth();
  return (
    <Pressable accessibilityRole="button" style={{ paddingHorizontal: 14 }} onPress={() =>
      Alert.alert("Log out?", "", [{ text: "Cancel", style: "cancel" },
        { text: "Log out", style: "destructive", onPress: async () => { await signOut(); router.replace("/login"); } }])}>
      <Text style={{ color: colors.brand, fontWeight: "700" }}>Log out</Text>
    </Pressable>
  );
}
