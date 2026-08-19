import { ArrowRight, BarChart3, BookOpen, CalendarDays, Clock3, Target } from "lucide-react";
import AppShell from "../components/AppShell";
import PrimaryButton from "@/components/ui/primary-button";

export default function ProgressPage() {
  return (
    <AppShell active="Progress">
      <main className="workspace progress-workspace">
        <header className="workspace-header">
          <div><span className="workspace-kicker">Your preparation, honestly measured</span><h1>Progress</h1><p>Your practice history will turn into useful direction here.</p></div>
          <div className="workspace-badge"><CalendarDays size={15} /> No activity yet</div>
        </header>

        <section className="progress-stat-grid">
          <article><span className="stat-icon"><Target size={19} /></span><div><small>Overall accuracy</small><strong>—</strong><p>Complete a set to begin</p></div></article>
          <article><span className="stat-icon"><Clock3 size={19} /></span><div><small>Practice time</small><strong>—</strong><p>No sessions recorded</p></div></article>
          <article><span className="stat-icon"><BookOpen size={19} /></span><div><small>Questions attempted</small><strong>—</strong><p>Your attempts appear here</p></div></article>
        </section>

        <div className="dashboard-grid">
          <section className="dashboard-card accuracy-card">
            <header><div><span>Accuracy over time</span><small>Based on completed sets</small></div><span className="card-tag">Awaiting data</span></header>
            <div className="empty-visual"><div className="ghost-chart"><span /><span /><span /><span /><span /><span /><span /></div><BarChart3 size={24} /><strong>Your trend starts with one practice set</strong><p>We will never populate this chart with sample performance.</p><PrimaryButton href="/login?next=/practice" size="sm">Start practising <ArrowRight size={15} /></PrimaryButton></div>
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
