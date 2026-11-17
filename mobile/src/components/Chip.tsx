import { Pressable, Text } from "react-native";
import { colors } from "@/lib/theme";

export function Chip({ label, active, onPress }: { label: string; active: boolean; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} accessibilityRole="button" accessibilityState={{ selected: active }}
      style={{ paddingHorizontal: 12, paddingVertical: 7, borderRadius: 999, marginRight: 6, marginBottom: 6, borderWidth: 1,
        borderColor: active ? colors.brand : colors.line, backgroundColor: active ? colors.brand : colors.surface }}>
      <Text style={{ color: active ? "#fff" : colors.ink2, fontWeight: "600" }}>{label}</Text>
    </Pressable>
  );
}
