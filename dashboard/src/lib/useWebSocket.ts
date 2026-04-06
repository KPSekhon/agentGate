"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import type { AuditLog } from "./types";

const MAX_ENTRIES = 50;

export function useAuditWebSocket() {
  const [entries, setEntries] = useState<AuditLog[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const retriesRef = useRef(0);

  const connect = useCallback(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${protocol}//localhost:8000/audit/live`);

    ws.onopen = () => {
      setConnected(true);
      retriesRef.current = 0;
    };

    ws.onmessage = (event) => {
      const entry: AuditLog = JSON.parse(event.data);
      setEntries((prev) => [entry, ...prev].slice(0, MAX_ENTRIES));
    };

    ws.onclose = () => {
      setConnected(false);
      if (retriesRef.current < 5) {
        retriesRef.current += 1;
        const delay = Math.min(1000 * 2 ** retriesRef.current, 16000);
        setTimeout(connect, delay);
      }
    };

    ws.onerror = () => ws.close();
    wsRef.current = ws;
  }, []);

  useEffect(() => {
    connect();
    return () => wsRef.current?.close();
  }, [connect]);

  return { entries, connected };
}
