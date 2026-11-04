import Svg, { Circle, Polyline, Rect, Text as SvgText } from "react-native-svg";
import { colors } from "@/lib/theme";
import type { Route } from "@/lib/types";

/** Top-down store map with the optimised walking path. Aisle changes happen only via the
 * front or back cross-aisle, the same model the API's route planner uses. */
export function StoreMap({ route, done }: { route: Route; done: Set<number> }) {
  const { aisles, rows } = route.layout;
  const W = 44, RH = 26, TOP = 26, H = TOP * 2 + (rows + 1) * RH, width = 24 + aisles * W;
  const xy = (a: number, r: number): [number, number] => [24 + (a - 1) * W + 12, H - TOP - r * RH];
  const pts: [number, number][] = [[route.start.aisle, 0], ...route.steps.map((s) => [s.aisle, s.row] as [number, number]), [route.end.aisle, 0]];
  const path: [number, number][] = [xy(...pts[0])];
  for (let i = 1; i < pts.length; i++) {
    const [a1, r1] = pts[i - 1], [a2, r2] = pts[i];
    if (a1 !== a2) {
      const via = r1 + r2 <= rows + 1 - r1 + (rows + 1 - r2) ? 0 : rows + 1;
      path.push(xy(a1, via), xy(a2, via));
    }
    path.push(xy(a2, r2));
  }
  return (
    <Svg width="100%" height={H} viewBox={`0 0 ${width} ${H}`}>
      <Rect width={width} height={H} rx={12} fill={colors.surface2} />
      {Array.from({ length: aisles }, (_, i) => (
        <Rect key={i} x={24 + i * W} y={H - TOP - rows * RH - RH / 2} width={24} height={rows * RH} rx={4} fill="#d8dfd5" />
      ))}
      {Array.from({ length: aisles }, (_, i) => (
        <SvgText key={`t${i}`} x={24 + i * W + 12} y={H - TOP - (rows * RH) / 2} fontSize={9} fontWeight="700" fill={colors.muted} textAnchor="middle">{i + 1}</SvgText>
      ))}
      <Polyline points={path.map((p) => p.join(",")).join(" ")} fill="none" stroke={colors.brand} strokeWidth={2.5} strokeDasharray="5 4" />
      {route.steps.map((s) => {
        const [x, y] = xy(s.aisle, s.row);
        return [<Circle key={`c${s.step}`} cx={x} cy={y} r={8} fill={done.has(s.step) ? colors.muted : colors.brand} />,
          <SvgText key={`n${s.step}`} x={x} y={y + 3.5} fontSize={9} fontWeight="700" fill="#fff" textAnchor="middle">{s.step}</SvgText>];
      })}
      <SvgText x={xy(route.start.aisle, 0)[0]} y={H - 6} fontSize={9} fontWeight="700" textAnchor="middle" fill={colors.ink}>IN</SvgText>
      <SvgText x={xy(route.end.aisle, 0)[0]} y={H - 6} fontSize={9} fontWeight="700" textAnchor="middle" fill={colors.ink}>EXIT</SvgText>
    </Svg>
  );
}
