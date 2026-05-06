"use client";

import { useEffect } from "react";
import { useHiveStore } from "@/store/useHiveStore";

export function SseProvider() {
  const { setHiveStatus, setConnected } = useHiveStore();

  useEffect(() => {
    let es: EventSource;
    let retry: ReturnType<typeof setTimeout>;

    function connect() {
      es = new EventSource("/api/stream");
      es.onopen = () => setConnected(true);
      es.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          if (msg.type === "status" && msg.data) setHiveStatus(msg.data);
        } catch {}
      };
      es.onerror = () => {
        setConnected(false);
        es.close();
        retry = setTimeout(connect, 5000);
      };
    }
    connect();
    return () => {
      clearTimeout(retry);
      es?.close();
    };
  }, [setHiveStatus, setConnected]);

  return null;
}
