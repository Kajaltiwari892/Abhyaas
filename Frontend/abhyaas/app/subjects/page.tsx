"use client";

import { ArrowRight, BookOpen, Globe2, Languages, Sigma } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { getSubjects, type Subject } from "@/lib/study-api";
import AppShell from "../components/AppShell";
import { useAuth } from "../components/AuthProvider";
import PracticeWorkspace from "../practice/PracticeWorkspace";
import p from "../practice/practice.module.css";
import s from "./subjects.module.css";

export default function SubjectsPage() {
  const { user } = useAuth();
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [selected, setSelected] = useState<string>();
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let alive = true;
    getSubjects().then((data) => { if (alive) { setSubjects(data); setError(""); } }).catch((e) => { if (alive) setError(e instanceof Error ? e.message : "Could not load subjects."); });
    return () => { alive = false; };
  }, [retry]);
  return <AppShell active="Subjects">{selected ? <PracticeWorkspace key={(user?.id ?? "guest") + selected} initialSubject={selected} onBack={() => setSelected(undefined)} /> : <main className={p.workspace}>
    <header className={p.header}><div><span className={p.eyebrow}><BookOpen size={14} /> Choose your focus</span><h1>Subjects</h1></div><Link href="/practice?view=history" className={p.secondary}>Practice history <ArrowRight size={14} /></Link></header>
    <p className={p.muted}>Choose a subject, then practice here. Topic filters, larger sets, saved progress and results — in one place.</p>
    {error && <div className={p.error} role="alert">{error} <button onClick={() => setRetry((v) => v+1)}>Retry</button></div>}
    <div className={s.subjects} role="group" aria-label="Choose a subject">{subjects.map((item) => {
      const Icon = item.slug === "english" ? Languages : item.slug === "general-knowledge" ? Globe2 : Sigma;
      return <button key={item.id} onClick={() => setSelected(item.slug)}><span className={s.icon}><Icon size={22} /></span><span><strong>{item.name}</strong><small>{item.slug === "elementary-mathematics" ? "CDS · not required for OTA" : "CDS / OTA"}</small><small>{item.topics.filter((t) => t.question_count > 0).length} available topics · {item.question_count} questions</small></span><ArrowRight size={16} /></button>;
    })}</div>
    {!subjects.length && !error && <p className={p.muted} role="status">Loading subjects…</p>}
  </main>}</AppShell>;
}
