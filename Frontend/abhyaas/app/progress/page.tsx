"use client";

import { ArrowRight, BarChart3, BookOpen, CalendarDays, Clock3, Target } from "lucide-react";
import AppShell from "../components/AppShell";
import { useAuth } from "../components/AuthProvider";
import PrimaryButton from "@/components/ui/primary-button";

export default function ProgressPage() {
  const { user } = useAuth();

  const firstName = user?.name.trim().split(/\s+/)[0];

  return (
    <AppShell active="Progress">
      <main className="workspace progress-workspace">
        <header className="workspace-header">
          <div><span className="workspace-kicker">{user ? `Signed in as ${user.email}` : "Your preparation, honestly measured"}</span><h1>{firstName ? `Welcome, ${firstName}.` : "Progress"}</h1><p>{user ? `${user.name}, your practice history and progress will appear here.` : "Loading your preparation space…"}</p></div>
          <div className="workspace-badge"><CalendarDays size={15} /> {user?.is_verified ? "Verified account" : "No activity yet"}</div>
        </header>

        <section className="progress-stat-grid">
          <article><span className="stat-icon"><Target size={19} /></span><div><small>Overall accuracy</small><strong>—</strong><p>Complete a set to begin</p></div></article>
          <article><span className="stat-icon"><Clock3 size={19} /></span><div><small>Practice time</small><strong>—</strong><p>No sessions recorded</p></div></article>
          <article><span className="stat-icon"><BookOpen size={19} /></span><div><small>Questions attempted</small><strong>—</strong><p>Your attempts appear here</p></div></article>
        </section>

        <div className="dashboard-grid">
          <section className="dashboard-card accuracy-card">
            <header><div><span>Accuracy over time</span><small>Based on completed sets</small></div><span className="card-tag">Awaiting data</span></header>
            <div className="empty-visual"><div className="ghost-chart"><span /><span /><span /><span /><span /><span /><span /></div><BarChart3 size={24} /><strong>Your trend starts with one practice set</strong><p>We will never populate this chart with sample performance.</p><PrimaryButton href="/practice" size="sm">Start practising <ArrowRight size={15} /></PrimaryButton></div>
          </section>
          <section className="dashboard-card strength-card">
            <header><div><span>Subject strength</span><small>Accuracy by syllabus area</small></div></header>
            <div className="subject-empty-list">{["English", "General Knowledge", "Elementary Mathematics"].map((subject) => <div key={subject}><span>{subject}</span><div><i /></div><small>—</small></div>)}</div>
            <p className="card-footnote">Strengths and weak topics appear only after relevant attempts.</p>
          </section>
          <section className="dashboard-card history-card">
            <header><div><span>Practice history</span><small>Your recent study sessions</small></div></header>
            <div className="history-empty"><CalendarDays size={25} /><strong>No practice history yet</strong><p>Completed sets and mock papers will be logged here by date.</p></div>
          </section>
        </div>
      </main>
    </AppShell>
  );
}
