"use client";

import { ArrowRight, BarChart3, BookOpen, CalendarDays, Clock3, Target } from "lucide-react";
import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import AppShell from "../components/AppShell";
import PreparationTarget from "../components/PreparationTarget";
import { useAuth } from "../components/AuthProvider";
import PrimaryButton from "@/components/ui/primary-button";
import { ApiError } from "@/lib/auth-api";
import { getProgressDashboard, type ProgressDashboard } from "@/lib/study-api";
import TodayPlan from "./TodayPlan";
import planStyles from "./today-plan.module.css";

const formatDuration = (seconds: number) => seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m`;
const StudentProgressChart = dynamic(() => import("../components/StudentProgressChart"), {
  loading: () => <ChartSkeleton />,
  ssr: false,
});

function ChartSkeleton() {
  return <div className="empty-visual" role="status" aria-label="Loading progress chart"><div className="ghost-chart" aria-hidden="true"><span /><span /><span /><span /><span /><span /><span /></div><p>Loading your progress…</p></div>;
}

export default function ProgressPage() {
  const { user } = useAuth();
  return <ProgressContent key={user?.id ?? "guest"} />;
}

function ProgressContent() {
  const { user, accessToken } = useAuth();
  const userId = user?.id;
  const [dashboard, setDashboard] = useState<ProgressDashboard | null>(null);
  const [error, setError] = useState("");
  const firstName = user?.name.trim().split(/\s+/)[0];

  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    try {
      const cached = window.localStorage.getItem(`abhyaas-progress-v1:${userId}`);
      if (cached) {
        const parsed = JSON.parse(cached) as ProgressDashboard;
        queueMicrotask(() => { if (!cancelled) setDashboard(parsed); });
      }
    } catch {
      // A corrupt or unavailable cache should never block a fresh request.
    }
    return () => { cancelled = true; };
  }, [userId]);

  useEffect(() => {
    if (!accessToken || !userId) return;
    let cancelled = false;
    getProgressDashboard(accessToken).then(data => {
      if (cancelled) return;
      setDashboard(data);
      setError("");
      try { window.localStorage.setItem(`abhyaas-progress-v1:${userId}`, JSON.stringify(data)); } catch { /* storage can be unavailable */ }
    }).catch((reason: unknown) => {
      if (!cancelled) setError(reason instanceof ApiError ? reason.message : "Progress could not be loaded.");
    });
    return () => { cancelled = true; };
  }, [accessToken, userId]);

  useEffect(() => { if (error) toast.error("Progress could not be loaded", { description: error, id: "progress-error" }); }, [error]);

  const hasAttempts = Boolean(dashboard?.completed_sets);

  return <AppShell active="Progress"><main className={`workspace progress-workspace ${planStyles.page}`}>
    <header className={planStyles.pageHeader}><div><h1>{firstName ? `Welcome, ${firstName}.` : "Your study space"}</h1><p>Your plan for today. Your progress over time.</p></div><a href="#stats">View progress <ArrowRight size={14} /></a></header>
    <TodayPlan key={user?.id ?? "guest"} />
    <section id="stats" className={planStyles.statsHeading}><h2>Your progress</h2><span>{dashboard ? `${dashboard.completed_sets} completed sets` : "Loading activity"}</span></section>
    <PreparationTarget />
    <div className="mistake-notebook-shortcut"><BookOpen size={18} /><div><strong>Mistake notebook</strong><span>Turn wrong and skipped answers into quick revision.</span></div><PrimaryButton href="/mistake-notebook" size="sm">Open notebook <ArrowRight size={14} /></PrimaryButton></div>
    <section className="progress-stat-grid" aria-label="All-time progress across all subjects">
      <article><span className="stat-icon"><Target size={19} /></span><div><small>Overall accuracy</small><strong>{dashboard?.overall_accuracy != null ? `${dashboard.overall_accuracy}%` : "—"}</strong><p>{hasAttempts ? `${dashboard?.correct_answers} correct answers` : "Complete a set to begin"}</p></div></article>
      <article><span className="stat-icon"><Clock3 size={19} /></span><div><small>Practice time</small><strong>{dashboard ? formatDuration(dashboard.practice_seconds) : "—"}</strong><p>{hasAttempts ? "Across completed sessions" : "No sessions recorded"}</p></div></article>
      <article><span className="stat-icon"><BookOpen size={19} /></span><div><small>Questions attempted</small><strong>{dashboard?.questions_attempted ?? "—"}</strong><p>{hasAttempts ? `${dashboard?.completed_sets} completed sets` : "Your attempts appear here"}</p></div></article>
    </section>
    <div className="dashboard-grid">
      <section className="dashboard-card accuracy-card"><header><div><span>Accuracy over time</span><small>Based only on completed sets</small></div><span className="card-tag">{hasAttempts ? "Live data" : "Awaiting data"}</span></header>
        {!dashboard ? <ChartSkeleton /> : !hasAttempts ? <div className="empty-visual"><div className="ghost-chart"><span /><span /><span /><span /><span /><span /><span /></div><BarChart3 size={24} /><strong>Your trend starts with one practice set</strong><p>We never populate this chart with sample performance.</p><PrimaryButton href="/subjects" size="sm">Start practising <ArrowRight size={15} /></PrimaryButton></div>
          : <StudentProgressChart trend={dashboard?.trend ?? []} />}
      </section>
      <section className="dashboard-card strength-card"><header><div><span>Subject strength</span><small>Accuracy by syllabus area</small></div></header><div className="subject-empty-list">{(dashboard?.subject_strengths ?? []).map(item => <div key={item.subject}><span>{item.subject}</span><div><i style={{ width: `${item.accuracy ?? 0}%` }} /></div><small>{item.accuracy == null ? "—" : `${item.accuracy}%`}</small></div>)}</div><p className="card-footnote">A subject receives a strength score only after relevant attempts.</p></section>
      <section className="dashboard-card history-card"><header><div><span>Practice history</span><small>Your recent completed sessions</small></div></header>
        {!dashboard ? <div className="history-empty" role="status">Loading your history…</div> : !hasAttempts ? <div className="history-empty"><CalendarDays size={25} /><strong>No practice history yet</strong><p>Completed sets will be logged here by date.</p></div>
          : <div className="practice-history-list">{dashboard?.history.map(item => <article key={item.attempt_id}><div><strong>{item.subject}</strong><small>{item.topic ?? "Mixed topics"} · {new Date(item.completed_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}</small></div><span>{item.scored_questions ? `${item.correct_answers}/${item.scored_questions}` : `${item.total_questions} done`}</span><b>{item.accuracy == null ? "Under review" : `${item.accuracy}%`}</b><time>{formatDuration(item.duration_seconds)}</time></article>)}</div>}
      </section>
    </div>
  </main></AppShell>;
}
