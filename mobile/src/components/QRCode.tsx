import QR from "qrcode";
import { useMemo } from "react";
import Svg, { Path, Rect } from "react-native-svg";

/** Renders a QR code fully offline (the exit gate works even with no signal in the store). */
export function QRCode({ value, size = 240 }: { value: string; size?: number }) {
  const { d, n } = useMemo(() => {
    const qr = QR.create(value, { errorCorrectionLevel: "M" });
    const count = qr.modules.size;
    let path = "";
    for (let y = 0; y < count; y++)
      for (let x = 0; x < count; x++) if (qr.modules.get(x, y)) path += `M${x + 2} ${y + 2}h1v1h-1z`;
    return { d: path, n: count + 4 };
  }, [value]);
  return (
    <Svg width={size} height={size} viewBox={`0 0 ${n} ${n}`}>
      <Rect width={n} height={n} fill="#fff" />
      <Path d={d} fill="#000" />
    </Svg>
  );
}
