import { ReactNode } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, TextInputProps, View, ViewStyle } from "react-native";
import { colors, radius } from "@/lib/theme";

export function Button({ title, onPress, variant = "primary", disabled, loading, style, small }: {
  title: string; onPress?: () => void; variant?: "primary" | "secondary" | "danger" | "ghost";
  disabled?: boolean; loading?: boolean; style?: ViewStyle; small?: boolean;
}) {
  const bg = { primary: colors.brand, secondary: colors.surface, danger: colors.danger, ghost: "transparent" }[variant];
  const fg = variant === "secondary" || variant === "ghost" ? colors.brand : "#fff";
  return (
    <Pressable onPress={onPress} disabled={disabled || loading} accessibilityRole="button"
      style={({ pressed }) => [s.btn, small && s.btnSm, { backgroundColor: bg, opacity: disabled ? 0.5 : pressed ? 0.85 : 1 },
        variant === "secondary" && { borderWidth: 1, borderColor: colors.line }, style]}>
      {loading ? <ActivityIndicator color={fg} /> : <Text style={[s.btnText, small && { fontSize: 13 }, { color: fg }]}>{title}</Text>}
    </Pressable>
  );
}

export const Card = ({ children, style }: { children: ReactNode; style?: ViewStyle }) => <View style={[s.card, style]}>{children}</View>;

export const Badge = ({ text, tone = "neutral" }: { text: string; tone?: "neutral" | "ok" | "warn" | "danger" | "info" }) => {
  const c = { neutral: [colors.surface2, colors.ink2], ok: [colors.brandSoft, colors.brand], warn: [colors.warnSoft, colors.warn],
    danger: [colors.dangerSoft, colors.danger], info: [colors.infoSoft, colors.info] }[tone];
  return <Text style={[s.badge, { backgroundColor: c[0], color: c[1] }]}>{text}</Text>;
};

export const Input = (p: TextInputProps) => <TextInput placeholderTextColor={colors.muted} {...p} style={[s.input, p.style]} />;

export const H1 = ({ children }: { children: ReactNode }) => <Text style={s.h1}>{children}</Text>;
export const H2 = ({ children }: { children: ReactNode }) => <Text style={s.h2}>{children}</Text>;
export const Muted = ({ children }: { children: ReactNode }) => <Text style={s.muted}>{children}</Text>;

export const Row = ({ children, style }: { children: ReactNode; style?: ViewStyle }) =>
  <View style={[{ flexDirection: "row", alignItems: "center", gap: 8 }, style]}>{children}</View>;

export function SummaryLine({ label, value, bold }: { label: string; value: string; bold?: boolean }) {
  return <Row style={{ justifyContent: "space-between", paddingVertical: 3 }}>
    <Text style={[{ color: colors.ink2 }, bold && s.bold]}>{label}</Text><Text style={bold ? s.bold : { color: colors.ink }}>{value}</Text></Row>;
}

export const s = StyleSheet.create({
  btn: { paddingVertical: 13, paddingHorizontal: 18, borderRadius: 12, alignItems: "center", justifyContent: "center" },
  btnSm: { paddingVertical: 7, paddingHorizontal: 12, borderRadius: 9 },
  btnText: { fontWeight: "700", fontSize: 15 },
  card: { backgroundColor: colors.surface, borderRadius: radius, borderWidth: 1, borderColor: colors.line, padding: 16, marginBottom: 12 },
  badge: { alignSelf: "flex-start", paddingHorizontal: 8, paddingVertical: 2, borderRadius: 999, fontSize: 12, fontWeight: "700", overflow: "hidden" },
  input: { borderWidth: 1, borderColor: colors.line, borderRadius: 11, paddingHorizontal: 12, paddingVertical: 11, backgroundColor: "#fff", fontSize: 15, color: colors.ink },
  h1: { fontSize: 24, fontWeight: "800", color: colors.ink, marginBottom: 6 },
  h2: { fontSize: 17, fontWeight: "700", color: colors.ink, marginBottom: 8 },
  muted: { color: colors.muted, fontSize: 13 },
  bold: { fontWeight: "800", fontSize: 17, color: colors.ink },
  screen: { flex: 1, backgroundColor: colors.bg },
  pad: { padding: 16, paddingBottom: 40 },
});
