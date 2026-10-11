import { BookOpen, FileText, GraduationCap, NotebookPen, Sparkles, Swords, Target } from "lucide-react";
import Link from "next/link";
import s from "./workspace-skeleton.module.css";

const destinations = [
  ["Daily plan & progress", "/progress", Target],
  ["Subjects", "/subjects", GraduationCap],
  ["Previous papers", "/papers", FileText],
  ["Mistake notebook", "/mistake-notebook", NotebookPen],
  ["Doubt solver", "/doubt-solver", BookOpen],
] as const;

// Only public navigation and placeholders: never mount a protected page or read
// a student's saved data while their session is still being restored.
export default function WorkspaceSkeleton({ pathname = "/progress" }: { pathname?: string }) {
  const title = pathname.startsWith("/papers") ? "Previous papers"
    : pathname.startsWith("/subjects") || pathname.startsWith("/practice") ? "Subjects"
    : pathname.startsWith("/doubt-solver") ? "Doubt solver"
    : pathname.startsWith("/mistake-notebook") ? "Mistake notebook"
    : pathname.startsWith("/exam-info") ? "Exam info"
    : pathname.startsWith("/profile") ? "Your profile" : "Your study space";
  return <div className="app-shell">
    <header className="app-topbar">
      <Link href="/" className="app-brand"><span><Swords size={18} /></span> ABHYAAS</Link>
      <span className={s.status} role="status" aria-live="polite">Opening your study space…</span>
    </header>
    <aside className={`app-sidebar ${s.sidebar}`}>
      <div className="sidebar-intro"><span className="sidebar-intro-mark"><Sparkles size={16} /></span><div className="sidebar-intro-copy"><strong>Study workspace</strong><small>Your CDS preparation, together</small></div></div>
      <nav className="sidebar-navigation" aria-label="Study navigation">
        {destinations.map(([label, href, Icon]) => <Link key={href} href={href} className={pathname.startsWith(href) ? "active" : ""}><span className="sidebar-nav-icon"><Icon size={17} /></span><span className="sidebar-nav-copy">{label}</span></Link>)}
      </nav>
    </aside>
    <div className="app-content"><main className={s.workspace} aria-busy="true" aria-label={`Loading ${title}`}>
      <h1>{title}</h1>
      <div className={s.line} aria-hidden="true" />
      <div className={s.feature} aria-hidden="true"><div className={s.line} /><div className={s.line} /><div className={s.line} /><div className={s.action} /></div>
      <div className={s.grid} aria-hidden="true">{[0, 1, 2].map(item => <div className={s.card} key={item}><div className={s.line} /><div className={s.value} /><div className={s.line} /></div>)}</div>
    </main></div>
    <nav className="app-bottom-nav" aria-label="Application navigation">
      {destinations.map(([label, href, Icon]) => <Link key={href} href={href} className={pathname.startsWith(href) ? "active" : ""}><Icon size={19} /><span>{href === "/progress" ? "Today" : href === "/papers" ? "Papers" : href === "/mistake-notebook" ? "Mistakes" : href === "/doubt-solver" ? "Ask AI" : label}</span></Link>)}
    </nav>
  </div>;
}
