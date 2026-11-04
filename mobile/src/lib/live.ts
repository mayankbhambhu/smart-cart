import { useEffect, useRef } from "react";
import { getToken } from "./api";
import { API_URL } from "./config";

export type LiveEvent = { channel: string; event: string; data: Record<string, any> };

/** Subscribe to API WebSocket channels (e.g. ["list:3"]). Reconnects with backoff. */
export function useLive(channels: string[], onEvent: (e: LiveEvent) => void) {
  const handler = useRef(onEvent);
  handler.current = onEvent;
  const key = channels.join(",");

  useEffect(() => {
    let ws: WebSocket | null = null;
    let closed = false;
    let retry = 1000;
    let ping: ReturnType<typeof setInterval>;
    const connect = () => {
      const token = getToken();
      if (!token || closed) return;
      ws = new WebSocket(`${API_URL.replace(/^http/, "ws")}/ws?token=${encodeURIComponent(token)}&channels=${encodeURIComponent(key)}`);
      ws.onopen = () => { retry = 1000; };
      ws.onmessage = (m) => { if (m.data !== "pong") handler.current(JSON.parse(String(m.data))); };
      ws.onclose = () => { if (!closed) setTimeout(connect, (retry = Math.min(retry * 2, 15000))); };
      ping = setInterval(() => ws?.readyState === 1 && ws.send("ping"), 25000);
    };
    connect();
    return () => { closed = true; clearInterval(ping); ws?.close(); };
  }, [key]);
}
