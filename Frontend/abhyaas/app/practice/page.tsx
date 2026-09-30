"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import AppShell from "../components/AppShell";
import { useAuth } from "../components/AuthProvider";
import PracticeWorkspace from "./PracticeWorkspace";

function PracticeRoute() {
  const params = useSearchParams();
  const { user } = useAuth();
  return <PracticeWorkspace key={`${user?.id ?? "guest"}:${params.toString()}`} initialSubject={params.get("subject") || "english"} initialTopic={params.get("topic") || ""} initialView={params.get("view") === "history" ? "history" : "practice"} />;
}

export default function PracticePage() {
  return <AppShell active="Practice"><Suspense fallback={<p>Loading practice…</p>}><PracticeRoute /></Suspense></AppShell>;
}
