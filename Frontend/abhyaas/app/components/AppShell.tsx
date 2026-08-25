"use client";

import { BarChart3, BookOpen, Bot, FileText, GraduationCap, Home, Info, LogOut, Menu, Swords, Target, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import ExamSwitcher from "./ExamSwitcher";
import { useAuth } from "./AuthProvider";

const desktopItems = [
  { label: "Home", href: "/", icon: Home },
  { label: "Exam info", href: "/exam-info", icon: Info },
  { label: "Subjects", href: "/subjects", icon: GraduationCap },
  { label: "Practice", href: "/practice", icon: Target },
  { label: "Doubt solver", href: "/doubt-solver", icon: Bot },
  { label: "Previous papers", href: "/papers", icon: FileText },
  { label: "Progress", href: "/progress", icon: BarChart3 },
  { label: "About", href: "/about", icon: BookOpen },
];

const mobileItems = desktopItems.filter(({ label }) => ["Home", "Practice", "Doubt solver", "Previous papers", "Progress"].includes(label));

export default function AppShell({ active, children }: { active: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const { user, signOut } = useAuth();

  const initials = user?.name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");

  return (
    <div className="app-shell">
      <header className="app-topbar">
        <Link href="/" className="app-brand"><span><Swords size={18} /></span> ABHYAAS</Link>
        <ExamSwitcher compact />
        <div className="app-context app-user-context">
          {user ? <span className="app-user-avatar">{initials}</span> : <span className="status-dot" />}
          <span className="app-user-copy"><strong>{user?.name ?? "Study workspace"}</strong><small>{user?.email ?? "CDS preparation"}</small></span>
          {user && <button className="app-signout" type="button" onClick={() => void signOut()} aria-label="Sign out"><LogOut size={15} /></button>}
        </div>
        <button className="app-menu-toggle" onClick={() => setOpen(!open)} aria-label="Toggle navigation">{open ? <X /> : <Menu />}</button>
      </header>
      <aside className={`app-sidebar ${open ? "is-open" : ""}`}>
        <div className="sidebar-label">Workspace</div>
        <nav>
          {desktopItems.map(({ label, href, icon: Icon }) => <Link className={active === label ? "active" : ""} href={href} key={label} onClick={() => setOpen(false)}><Icon size={18} /><span>{label}</span></Link>)}
        </nav>
        <div className="sidebar-note"><BookOpen size={16} /><div><strong>Official details</strong><span>Always verify dates and eligibility in the latest UPSC notification.</span></div></div>
      </aside>
      <div className="app-content">{children}</div>
      <nav className="app-bottom-nav" aria-label="Application navigation">
        {mobileItems.map(({ label, href, icon: Icon }) => <Link className={active === label ? "active" : ""} href={href} key={label}><Icon size={19} /><span>{label === "Previous papers" ? "Papers" : label === "Doubt solver" ? "Ask AI" : label}</span></Link>)}
      </nav>
    </div>
  );
}
