"use client";

import { ArrowRight, BarChart3, BookOpen, CalendarDays, Clock3, Target } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import AppShell from "../components/AppShell";
import { useAuth } from "../components/AuthProvider";
import PrimaryButton from "@/components/ui/primary-button";
import { ApiError } from "@/lib/auth-api";
import { getProgressDashboard, type ProgressDashboard } from "@/lib/study-api";

const formatDuration = (seconds: number) => seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m`;

export default function ProgressPage() {
  const { user, accessToken } = useAuth();
  const [dashboard, setDashboard] = useState<ProgressDashboard | null>(null);
  const [error, setError] = useState("");
  const firstName = user?.name.trim().split(/\s+/)[0];

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    try {
      const cached = window.localStorage.getItem(`abhyaas-progress-v1:${user.id}`);
      if (cached) {
        const parsed = JSON.parse(cached) as ProgressDashboard;
        queueMicrotask(() => { if (!cancelled) setDashboard(parsed); });
      }
    } catch {
      // A corrupt or unavailable cache should never block a fresh request.
    }
    return () => { cancelled = true; };
  }, [user]);

  useEffect(() => {
    if (!accessToken || !user) return;
    let cancelled = false;
    getProgressDashboard(accessToken).then(data => {
      if (cancelled) return;
      setDashboard(data);
      setError("");
      try { window.localStorage.setItem(`abhyaas-progress-v1:${user.id}`, JSON.stringify(data)); } catch { /* storage can be unavailable */ }
    }).catch((reason: unknown) => {
      if (!cancelled) setError(reason instanceof ApiError ? reason.message : "Progress could not be loaded.");
    });
    return () => { cancelled = true; };
  }, [accessToken, user]);

  useEffect(() => { if (error) toast.error("Progress could not be loaded", { description: error, id: "progress-error" }); }, [error]);

  const hasAttempts = Boolean(dashboard?.completed_sets);

  return <AppShell active="Progress"><main className="workspace progress-workspace">
    <header className="workspace-header"><div><span className="workspace-kicker">{user ? `Signed in as ${user.email}` : "Your preparation, honestly measured"}</span><h1>{firstName ? `Welcome, ${firstName}.` : "Progress"}</h1><p>Your completed practice sets update this dashboard automatically.</p></div><div className="workspace-badge"><CalendarDays size={15} /> {dashboard ? `${dashboard.completed_sets} completed sets` : "Loading activity"}</div></header>
    <section className="progress-stat-grid">
      <article><span className="stat-icon"><Target size={19} /></span><div><small>Overall accuracy</small><strong>{dashboard?.overall_accuracy != null ? `${dashboard.overall_accuracy}%` : "—"}</strong><p>{hasAttempts ? `${dashboard?.correct_answers} correct answers` : "Complete a set to begin"}</p></div></article>
      <article><span className="stat-icon"><Clock3 size={19} /></span><div><small>Practice time</small><strong>{dashboard ? formatDuration(dashboard.practice_seconds) : "—"}</strong><p>{hasAttempts ? "Across completed sessions" : "No sessions recorded"}</p></div></article>
      <article><span className="stat-icon"><BookOpen size={19} /></span><div><small>Questions attempted</small><strong>{dashboard?.questions_attempted ?? "—"}</strong><p>{hasAttempts ? `${dashboard?.completed_sets} completed sets` : "Your attempts appear here"}</p></div></article>
    </section>
    <div className="dashboard-grid">
      <section className="dashboard-card accuracy-card"><header><div><span>Accuracy over time</span><small>Based only on completed sets</small></div><span className="card-tag">{hasAttempts ? "Live data" : "Awaiting data"}</span></header>
        {!hasAttempts ? <div className="empty-visual"><div className="ghost-chart"><span /><span /><span /><span /><span /><span /><span /></div><BarChart3 size={24} /><strong>Your trend starts with one practice set</strong><p>We never populate this chart with sample performance.</p><PrimaryButton href="/practice" size="sm">Start practising <ArrowRight size={15} /></PrimaryButton></div>
          : <div className="real-trend" aria-label="Accuracy trend">{dashboard?.trend.map((point, index) => <div key={`${point.date}-${index}`}><span style={{ height: `${Math.max(4, point.accuracy)}%` }} /><small>{point.accuracy}%</small><time>{new Date(point.date).toLocaleDateString("en-IN", { day: "2-digit", month: "short" })}</time></div>)}</div>}
      </section>
      <section className="dashboard-card strength-card"><header><div><span>Subject strength</span><small>Accuracy by syllabus area</small></div></header><div className="subject-empty-list">{(dashboard?.subject_strengths ?? []).map(item => <div key={item.subject}><span>{item.subject}</span><div><i style={{ width: `${item.accuracy ?? 0}%` }} /></div><small>{item.accuracy == null ? "—" : `${item.accuracy}%`}</small></div>)}</div><p className="card-footnote">A subject receives a strength score only after relevant attempts.</p></section>
      <section className="dashboard-card history-card"><header><div><span>Practice history</span><small>Your recent completed sessions</small></div></header>
        {!hasAttempts ? <div className="history-empty"><CalendarDays size={25} /><strong>No practice history yet</strong><p>Completed sets will be logged here by date.</p></div>
          : <div className="practice-history-list">{dashboard?.history.map(item => <article key={item.attempt_id}><div><strong>{item.subject}</strong><small>{item.topic ?? "Mixed topics"} · {new Date(item.completed_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}</small></div><span>{item.scored_questions ? `${item.correct_answers}/${item.scored_questions}` : `${item.total_questions} done`}</span><b>{item.accuracy == null ? "Key pending" : `${item.accuracy}%`}</b><time>{formatDuration(item.duration_seconds)}</time></article>)}</div>}
      </section>
    </div>
  </main></AppShell>;
}
