"use client";

import { BadgeCheck, BarChart3, BookOpen, Bot, ChevronDown, ChevronRight, FileText, GraduationCap, Home, Info, LogOut, Mail, Menu, ShieldCheck, Sparkles, Swords, Target, UserRound, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import ExamSwitcher from "./ExamSwitcher";
import { useAuth } from "./AuthProvider";
import NavigationHint from "./NavigationHint";

const desktopSections = [
  { label: "Learn", items: [
    { label: "Home", href: "/?view=home", icon: Home },
    { label: "Exam info", href: "/exam-info", icon: Info },
    { label: "Subjects", href: "/subjects", icon: GraduationCap },
  ] },
  { label: "Prepare", items: [
    { label: "Practice", href: "/practice", icon: Target },
    { label: "Doubt solver", href: "/doubt-solver", icon: Bot },
    { label: "Previous papers", href: "/papers", icon: FileText },
    { label: "Progress", href: "/progress", icon: BarChart3 },
  ] },
  { label: "Abhyaas", items: [
    { label: "About", href: "/about", icon: BookOpen },
    { label: "Privacy", href: "/privacy", icon: ShieldCheck },
  ] },
];

const desktopItems = desktopSections.flatMap((section) => section.items);

const mobileItems = desktopItems.filter(({ label }) => ["Home", "Practice", "Doubt solver", "Previous papers", "Progress"].includes(label));

export default function AppShell({ active, children }: { active: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
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
        <Link href="/?view=home" className="app-brand"><span><Swords size={18} /></span> ABHYAAS</Link>
        <ExamSwitcher compact />
        <div className="app-context app-user-context">
          {user ? <span className="app-user-avatar">{initials}</span> : <span className="status-dot" />}
          <span className="app-user-copy"><strong>{user?.name ?? "Study workspace"}</strong><small>{user?.email ?? "CDS preparation"}</small></span>
          {user && <button className="app-signout" type="button" onClick={() => void signOut()} aria-label="Sign out"><LogOut size={15} /></button>}
        </div>
        <button className="app-menu-toggle" onClick={() => setOpen(!open)} aria-label="Toggle navigation">{open ? <X /> : <Menu />}</button>
      </header>
      <aside className={`app-sidebar ${open ? "is-open" : ""}`}>
        <div className="sidebar-intro"><span><Sparkles size={13} /> Study workspace</span><small>Everything for your CDS prep</small></div>
        <nav className="sidebar-navigation">
          {desktopSections.map((section) => <section className="sidebar-nav-section" key={section.label}>
            <span className="sidebar-section-label">{section.label}</span>
            {section.items.map(({ label, href, icon: Icon }) => <Link className={active === label ? "active" : ""} href={href} key={label} onClick={() => setOpen(false)}>
              <span className="sidebar-nav-icon"><Icon size={17} /></span>
              <span className="sidebar-nav-copy">{label}</span>
              <ChevronRight className="sidebar-nav-arrow" size={14} />
              <NavigationHint />
            </Link>)}
          </section>)}
        </nav>
        <div className={`sidebar-profile ${profileOpen ? "is-open" : ""}`}>
          <button type="button" className="sidebar-profile-trigger" onClick={() => setProfileOpen((value) => !value)} aria-expanded={profileOpen}>
            <span className="sidebar-profile-avatar">{initials || <UserRound size={17} />}</span>
            <span><strong>{user?.name ?? "Your profile"}</strong><small>View profile</small></span>
            <ChevronDown size={16} />
          </button>
          {profileOpen && <div className="sidebar-profile-details">
            <span><Mail size={14} /><span>{user?.email ?? "Sign in to see account details"}</span></span>
            {user && <span><BadgeCheck size={14} /><span>{user.is_verified ? "Verified account" : "Email verification pending"}</span></span>}
            {user && <button type="button" onClick={() => void signOut()}><LogOut size={14} /> Sign out</button>}
          </div>}
        </div>
      </aside>
      <div className="app-content">{children}</div>
      <nav className="app-bottom-nav" aria-label="Application navigation">
        {mobileItems.map(({ label, href, icon: Icon }) => <Link className={active === label ? "active" : ""} href={href} key={label}><Icon size={19} /><span>{label === "Previous papers" ? "Papers" : label === "Doubt solver" ? "Ask AI" : label}</span><NavigationHint /></Link>)}
      </nav>
    </div>
  );
}
