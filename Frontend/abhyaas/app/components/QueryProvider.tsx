"use client";

import { useEffect } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { getQueryClient } from "@/lib/query-client";

export default function QueryProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    // Remove snapshots left by the previous persistent progress cache.
    try {
      for (const key of Object.keys(localStorage)) {
        if (key.startsWith("abhyaas-progress-v1:")) localStorage.removeItem(key);
      }
    } catch { /* Storage can be disabled; the query cache is memory-only. */ }
  }, []);
  return <QueryClientProvider client={getQueryClient()}>{children}</QueryClientProvider>;
}
