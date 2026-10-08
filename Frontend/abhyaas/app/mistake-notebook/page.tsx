"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import AppShell from "../components/AppShell";
import { useAuth } from "../components/AuthProvider";
import MistakeNotebook from "../practice/MistakeNotebook";

function NotebookRoute() {
  const params = useSearchParams();
  const { user } = useAuth();
  return <MistakeNotebook key={`${user?.id ?? "guest"}:notebook`} revisionId={params.get("revision") || ""} />;
}

export default function NotebookPage() {
  return <AppShell active="Mistake notebook">
    <Suspense fallback={<p role="status">Opening your notebook…</p>}><NotebookRoute /></Suspense>
  </AppShell>;
}
